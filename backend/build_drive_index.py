"""
backend/build_drive_index.py

Build enhanced_index.json from real Google Drive folders, using a service
account. This is the Drive-backed sibling of build_local_index.py — same
chunking/extraction logic (via ingestion_common.py), same
PersistedInMemorySearch.ingest_documents() call, same output format, just a
different document source. Once this runs, retrieval and chat need zero
changes.

Prerequisites:
  1. A Google Cloud service account JSON key at the path pointed to by
     GOOGLE_DRIVE_CREDENTIALS_PATH in .env (default:
     backend/credentials/google_credentials.json).
  2. The parent Drive folder (containing all department subfolders) shared
     with the service account's client_email (Viewer access is enough) —
     permissions cascade to everything inside automatically.

Supported file types: Google Docs, .xlsx, .docx, .pdf, .txt, .md.
Native Google Sheets are intentionally skipped for now (export path differs
from uploaded .xlsx) — upload as .xlsx or convert to Sheets and ask to add
Sheets export support if needed.

Usage:
    python backend/build_drive_index.py
    python backend/build_drive_index.py --reset
    python backend/build_drive_index.py --folder "Md. Mozammel Haque"
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE.parent / ".env")

from app.features.rag_chatbot.ingestion_common import (
    FOLDER_DEPARTMENT_MAP,
    backup_index_if_exists,
    department_for_folder,
    extract_table_chunks_from_xlsx_bytes,
    extract_text_from_file,
    make_chunk_documents,
    make_table_chunk_documents,
)
from app.features.rag_chatbot.vector.google_drive_service import GoogleDriveService
from app.features.rag_chatbot.vector.persisted_inmemory_search import PersistedInMemorySearch

# ═══════════════════════════════════════════════════════════════════════
# MODULE: [OPS:ING-002] — the real Google Drive ingestion CLI, the
#          production-corpus-building path
#
# discover (Drive API via [OPS:DRIVE]) -> extract/chunk ([OPS:ING-001])
# -> embed ([OPS:IDX-002]) -> write JSON index ([OPS:IDX-004]) -> dual-
# write pgvector ([OPS:PVEC-003]). This exact same code is what runs
# both from the CLI and from the admin reindex endpoint's _run_reindex()
# [OPS:ADMIN-001a] (via a direct import of discover_documents +
# FOLDER_DEPARTMENT_MAP) — not a separate reimplementation.
# ═══════════════════════════════════════════════════════════════════════
DEFAULT_OUTPUT = HERE / "app/features/rag_chatbot/vector/enhanced_index.json"

GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
GOOGLE_SHEET_MIME = "application/vnd.google-apps.spreadsheet"
GOOGLE_FOLDER_MIME = "application/vnd.google-apps.folder"


def _looks_supported(file_name: str, mime_type: str) -> bool:
    if mime_type == GOOGLE_DOC_MIME:
        return True
    lower = file_name.lower()
    return lower.endswith((".xlsx", ".xlsm", ".docx", ".pdf", ".txt", ".md"))


# [OPS:ING-002b] _looks_supported() / _get_bytes() — MIME-type dispatch.
# _get_bytes() decides download_file() vs export_google_doc_as_text()
# [OPS:DRIVE-005] — a native Google Doc has no raw bytes to download,
# only an exportable representation, so the two extraction mechanics
# must diverge right here before any chunking logic runs.
def _get_bytes(drive: GoogleDriveService, file_info: Dict[str, Any]) -> bytes:
    if file_info["mime_type"] == GOOGLE_DOC_MIME:
        return drive.export_google_doc_as_text(file_info["id"])
    return drive.download_file(file_info["id"])


# ─────────────────────────────────────────────────────────────────────────
# [OPS:ING-002a] discover_documents() — the real Drive discovery loop
#
# API/CALL: [OPS:DRIVE-003] find_finance_folder() (resolve folder name
#       -> ID), [OPS:DRIVE-004] list_all_files_in_folder() (recursive
#       listing), [OPS:DRIVE-005] download_file()/export_google_doc_
#       as_text() (via _get_bytes() [OPS:ING-002b]).
# WHAT IT SKIPS: subfolders (already flattened by list_all_files_in_
#       folder's own recursion — seeing a folder entry here would mean
#       double-counting), native Google Sheets (export path differs
#       from uploaded .xlsx and isn't implemented — logged as [SKIP],
#       not silently dropped), and any file extension
#       _looks_supported() [OPS:ING-002b] doesn't recognize.
# NUANCE: Google Docs get a synthetic ".txt" suffix appended to their
#       dispatch_name before calling extract_text_from_file()
#       [OPS:ING-001b] — that function dispatches purely by file
#       extension, and a Google Doc's real Drive name usually has no
#       extension at all, so without this the doc's exported plain text
#       would silently return '' (no dispatch match) instead of being
#       processed.
# CALLED BY: main() [OPS:ING-002c] (CLI), discovery.py's _run_reindex()
#       [OPS:ADMIN-001a] (imported directly — the admin endpoint reuses
#       this exact function).
# ─────────────────────────────────────────────────────────────────────────
def discover_documents(drive: GoogleDriveService, folder_names: List[str]) -> List[Dict[str, Any]]:
    documents: List[Dict[str, Any]] = []

    for folder_name in folder_names:
        department = department_for_folder(folder_name)
        folder_id = drive.find_finance_folder(folder_name)  # generic "find folder by name" despite the name
        if not folder_id:
            print(f"[WARN] Folder not found or not shared with the service account: '{folder_name}'")
            continue

        files = drive.list_all_files_in_folder(folder_id, recursive=True)
        print(f"[INFO] '{folder_name}' -> {len(files)} files found")

        for file_info in files:
            if file_info["mime_type"] == GOOGLE_FOLDER_MIME:
                continue
            if file_info["mime_type"] == GOOGLE_SHEET_MIME:
                print(f"[SKIP] Native Google Sheet not yet supported: {file_info['name']}")
                continue
            if not _looks_supported(file_info["name"], file_info["mime_type"]):
                continue

            title = Path(file_info["name"]).stem
            is_excel = file_info["name"].lower().endswith((".xlsx", ".xlsm"))
            extra_metadata = {
                "drive_file_id": file_info["id"],
                "modified_time": file_info.get("modified_time"),
            }

            if is_excel:
                try:
                    raw = _get_bytes(drive, file_info)
                    table_chunks = extract_table_chunks_from_xlsx_bytes(raw)
                except Exception as e:
                    print(f"[WARN] Failed to extract '{file_info['name']}': {e}")
                    continue
                if not table_chunks:
                    continue
                documents.extend(
                    make_table_chunk_documents(
                        table_chunks,
                        id_prefix=f"drive_{file_info['id']}",
                        file_name=file_info["name"],
                        title=title,
                        department=department,
                        owner_folder=folder_name,
                        source="google_drive",
                        extra_metadata=extra_metadata,
                    )
                )
                continue

            # Google Docs get a .txt-equivalent name for extraction dispatch
            dispatch_name = file_info["name"] if file_info["mime_type"] != GOOGLE_DOC_MIME else file_info["name"] + ".txt"

            try:
                raw = _get_bytes(drive, file_info)
                text = extract_text_from_file(raw, dispatch_name)
            except Exception as e:
                print(f"[WARN] Failed to extract '{file_info['name']}': {e}")
                continue
            if not text.strip():
                continue

            documents.extend(
                make_chunk_documents(
                    text,
                    id_prefix=f"drive_{file_info['id']}",
                    file_name=file_info["name"],
                    title=title,
                    department=department,
                    owner_folder=folder_name,
                    source="google_drive",
                    extra_metadata=extra_metadata,
                )
            )
    return documents


# [OPS:ING-002c] main() — CLI entrypoint: connect + test_connection()
# [OPS:DRIVE-002], optional --reset (backup_index_if_exists()
# [OPS:ING-001e]), discover_documents() [OPS:ING-002a] -> ingest_
# documents() [OPS:IDX-004] -> dual-write via upsert_documents()
# [OPS:PVEC-003]. This exact sequence is what discovery.py's
# _run_reindex() [OPS:ADMIN-001a] reimplements for the HTTP-triggered
# path (not a call to this main(), but the same steps in the same order).
def main() -> None:
    parser = argparse.ArgumentParser(description="Build enhanced_index.json from Google Drive")
    parser.add_argument(
        "--folder",
        action="append",
        help="Specific owner folder name to ingest (repeatable). Defaults to all known folders.",
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Path to write enhanced_index.json")
    parser.add_argument("--reset", action="store_true", help="Overwrite any existing index instead of appending")
    args = parser.parse_args()

    output_path = Path(args.output)
    folder_names = args.folder or list(FOLDER_DEPARTMENT_MAP.keys())

    drive = GoogleDriveService()
    status = drive.test_connection()
    if not status.get("connected"):
        raise SystemExit(f"Could not connect to Google Drive: {status.get('error')}")
    print("[INFO] Connected to Google Drive")

    if args.reset and output_path.exists():
        backup_path = backup_index_if_exists(output_path)
        if backup_path:
            print(f"[INFO] Backed up existing index to {backup_path}")
        output_path.unlink()
        print(f"[INFO] Removed existing index at {output_path}")

    documents = discover_documents(drive, folder_names)
    if not documents:
        raise SystemExit(
            "No documents found. Check that the folders exist in Drive and are shared "
            "(Viewer access) with the service account's client_email."
        )

    print(f"[INFO] Discovered {len(documents)} chunks from Google Drive")

    index = PersistedInMemorySearch(index_path=output_path)
    index.ingest_documents(documents)

    stats = index.get_stats()
    print("[DONE] Index built:")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    # Dual-write into Supabase/pgvector (the real fallback path) using the
    # vectors already computed above — no-ops cleanly if Supabase isn't
    # configured yet.
    from app.features.rag_chatbot.vector.pgvector_store import is_configured, upsert_documents

    if is_configured():
        print("[INFO] Dual-writing to Supabase/pgvector...")
        pg_stats = upsert_documents(index.items)
        print(f"[DONE] pgvector dual-write: {pg_stats}")
    else:
        print("[INFO] Supabase not configured — skipping pgvector dual-write.")


if __name__ == "__main__":
    main()
