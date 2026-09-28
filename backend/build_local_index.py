"""
backend/build_local_index.py

Build enhanced_index.json from a local folder tree, without touching Google
Drive or requiring an OpenAI key. Each top-level folder under --source is
treated as a "department owner" folder (mirroring the real Drive structure
that discovery/scanner.py already expects). Supports .md, .txt, .xlsx, .docx,
and .pdf files.

This exists as a fast bring-up path: prove discovery -> extract -> chunk ->
embed -> search -> chat works end-to-end with mock embeddings today, then
later swap in real Google Drive discovery (see build_drive_index.py) without
changing the index format or the retrieval code at all.

Usage:
    python backend/build_local_index.py
    python backend/build_local_index.py --source backend/seed_docs --reset
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
# Load repo-root .env into os.environ *before* importing the search module,
# since it reads OPENAI_API_KEY / GEMINI_API_KEY / USE_MOCK_EMBEDDINGS via
# os.getenv() directly rather than through pydantic settings.
load_dotenv(HERE.parent / ".env")

from app.features.rag_chatbot.ingestion_common import (
    backup_index_if_exists,
    department_for_folder,
    extract_table_chunks_from_xlsx_bytes,
    extract_text_from_file,
    make_chunk_documents,
    make_table_chunk_documents,
)
from app.features.rag_chatbot.vector.persisted_inmemory_search import PersistedInMemorySearch

# ═══════════════════════════════════════════════════════════════════════
# MODULE: [OPS:ING-002-local] — local-folder ingestion CLI (the Drive-free
#          sibling of build_drive_index.py [OPS:ING-002])
#
# Same discover -> chunk -> embed -> index -> dual-write pipeline as the
# Drive path, just walking a local directory tree instead of calling the
# Google Drive API — used for fast local dev/bring-up with mock
# embeddings and zero external dependencies. See [OPS:ING-001]
# ingestion_common.py for the chunking/extraction logic shared with the
# real build_drive_index.py path.
# ═══════════════════════════════════════════════════════════════════════
DEFAULT_SOURCE = HERE / "seed_docs"
DEFAULT_OUTPUT = HERE / "app/features/rag_chatbot/vector/enhanced_index.json"
SUPPORTED_EXTENSIONS = ("*.md", "*.txt", "*.xlsx", "*.xlsm", "*.docx", "*.pdf")


# [OPS:ING-002-local-a] discover_documents() — walks source_dir/<owner
# folder>/<file>, dispatching Excel to make_table_chunk_documents()
# [OPS:ING-001d] (structure-preserving) and everything else through
# extract_text_from_file() [OPS:ING-001b] + make_chunk_documents(). Same
# structure as build_drive_index.py's discover_documents() [OPS:ING-002a]
# — deliberately, so both ingestion paths produce identical chunk shapes.
def discover_documents(source_dir: Path) -> List[Dict[str, Any]]:
    """Walk source_dir/<owner folder>/<file> and return chunk documents."""
    documents: List[Dict[str, Any]] = []
    for folder in sorted(p for p in source_dir.iterdir() if p.is_dir()):
        department = department_for_folder(folder.name)

        file_paths: List[Path] = []
        for pattern in SUPPORTED_EXTENSIONS:
            file_paths.extend(folder.glob(pattern))

        for file_path in sorted(file_paths):
            title = file_path.stem.replace("_", " ")
            is_excel = file_path.suffix.lower() in (".xlsx", ".xlsm")

            if is_excel:
                try:
                    table_chunks = extract_table_chunks_from_xlsx_bytes(file_path.read_bytes())
                except Exception as e:
                    print(f"[WARN] Failed to extract '{file_path.name}': {e}")
                    continue
                if not table_chunks:
                    continue
                documents.extend(
                    make_table_chunk_documents(
                        table_chunks,
                        id_prefix=f"local_{folder.name}_{file_path.stem}",
                        file_name=file_path.name,
                        title=title,
                        department=department,
                        owner_folder=folder.name,
                        source="local_seed",
                    )
                )
                continue

            try:
                text = extract_text_from_file(file_path.read_bytes(), file_path.name)
            except Exception as e:
                print(f"[WARN] Failed to extract '{file_path.name}': {e}")
                continue
            if not text.strip():
                continue

            documents.extend(
                make_chunk_documents(
                    text,
                    id_prefix=f"local_{folder.name}_{file_path.stem}",
                    file_name=file_path.name,
                    title=title,
                    department=department,
                    owner_folder=folder.name,
                    source="local_seed",
                )
            )
    return documents


# [OPS:ING-002-local-b] main() — CLI entrypoint: optional --reset (backs
# up + deletes the existing index via backup_index_if_exists()
# [OPS:ING-001e]), discover -> ingest_documents() [OPS:IDX-004] -> dual-
# write to pgvector via upsert_documents() [OPS:PVEC-003] if configured.
def main() -> None:
    parser = argparse.ArgumentParser(description="Build enhanced_index.json from local seed documents")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="Folder containing owner subfolders")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Path to write enhanced_index.json")
    parser.add_argument("--reset", action="store_true", help="Overwrite any existing index instead of appending")
    args = parser.parse_args()

    source_dir = Path(args.source)
    output_path = Path(args.output)

    if not source_dir.exists():
        raise SystemExit(f"Source folder not found: {source_dir}")

    if args.reset and output_path.exists():
        backup_path = backup_index_if_exists(output_path)
        if backup_path:
            print(f"[INFO] Backed up existing index to {backup_path}")
        output_path.unlink()
        print(f"[INFO] Removed existing index at {output_path}")

    documents = discover_documents(source_dir)
    if not documents:
        raise SystemExit(f"No supported documents found under {source_dir}")

    print(f"[INFO] Discovered {len(documents)} chunks from {source_dir}")

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
