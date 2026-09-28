"""
This file has the shared steps for turning a raw file — a PDF, Word
doc, or Excel sheet — into small, searchable pieces of text. Both ways
of building the search index (from a local test folder, or from real
Google Drive) use these exact same steps, so a document is chunked and
labeled the same way no matter where it came from.

Shared helpers used by build_local_index.py and build_drive_index.py so both
ingestion paths (local folder / real Google Drive) chunk and classify
documents identically. Deliberately simple — this is a fast, robust bring-up
path, not the speculative business-intelligence pipeline in
processing/document_processing_engine.py.
"""
# ─────────────────────────────────────────────────────────────────────────
# MODULE: [OPS:ING-001]
#
# What it does: shared helper functions for turning a document into
# search-ready pieces — deciding its department, splitting it into
# chunks, extracting text from each file format, building the final
# document dict, and backing up the index before a rebuild. Exists
# separately so both ingestion scripts (local test folder, real Google
# Drive) process documents identically.
# ─────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import io
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# [OPS:ING-001a] FOLDER_DEPARTMENT_MAP / department_for_folder()
#
# What it does: a fixed lookup table mapping each person's Drive folder
# name to the department they belong to. department_for_folder() checks
# whether a folder name CONTAINS one of these keys, so it still matches
# even if the real Drive folder name has extra text added, like "(PTIL)".
#
# Called by: build_drive_index.py's and build_local_index.py's
# discover_documents(), once per document being ingested.
FOLDER_DEPARTMENT_MAP = {
    "Riaz Uddin Sarker": "Admin",
    "Md. Mizanur Rahman (PTIL)": "Finance",
    "Khorshed Alam Babu": "Maintenance",
    "Md. Mozammel Haque": "HR",
    "Zahedul Islam Nizam": "Accounting",
    "Md. Alamin": "Commercial",
    "Monir Ahmed": "Executive",
}


def department_for_folder(folder_name: str) -> str:
    for owner, dept in FOLDER_DEPARTMENT_MAP.items():
        if owner in folder_name:
            return dept
    return "Unknown"


# ─────────────────────────────────────────────────────────────────────────
# [OPS:ING-001b] chunk_text() / extract_text_from_*() / extract_text_from_file()
#
# What it does: chunk_text() splits a long document into ~900-character
# pieces, but only at paragraph breaks — never in the middle of a
# paragraph, since a chunk that's cut mid-sentence produces a worse
# embedding. extract_text_from_file() looks at the file's extension and
# picks the right extraction method (PDF, DOCX, XLSX, or plain text).
# extract_text_from_xlsx_bytes() turns each spreadsheet into plain
# prose text — see extract_table_chunks_from_xlsx_bytes() below for the
# version that keeps the actual row/column structure instead.
#
# Called by: extract_text_from_file() is called directly by both
# ingestion scripts; chunk_text() is called by make_chunk_documents().
# ─────────────────────────────────────────────────────────────────────────
def chunk_text(text: str, max_chars: int = 900) -> List[str]:
    """Paragraph-aware chunking: pack paragraphs into ~max_chars windows."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: List[str] = []
    current = ""
    for para in paragraphs:
        if current and len(current) + len(para) + 2 > max_chars:
            chunks.append(current.strip())
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current.strip())
    return chunks or [text.strip()]


def extract_text_from_pdf_bytes(raw: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


def extract_text_from_docx_bytes(raw: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(raw))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    return "\n\n".join(parts)


def extract_text_from_xlsx_bytes(raw: bytes, rows_per_group: int = 12) -> str:
    """
    Flatten every sheet into readable text (used for non-table-aware callers).
    Prefer extract_table_chunks_from_xlsx_bytes() when structured row/column
    data needs to survive for downstream table/chart rendering.
    """
    import pandas as pd

    sheets = pd.read_excel(io.BytesIO(raw), sheet_name=None, dtype=str)
    parts: List[str] = []

    for sheet_name, df in sheets.items():
        df = df.dropna(how="all")
        if df.empty:
            continue
        columns = list(df.columns)
        parts.append(f"Sheet '{sheet_name}': columns = {', '.join(str(c) for c in columns)}. Total rows: {len(df)}.")

        records = df.fillna("").to_dict(orient="records")
        for i in range(0, len(records), rows_per_group):
            group = records[i : i + rows_per_group]
            lines = []
            for row in group:
                row_str = ", ".join(f"{k}={v}" for k, v in row.items() if str(v).strip())
                if row_str:
                    lines.append(row_str)
            if lines:
                parts.append(f"Sheet '{sheet_name}' rows {i + 1}-{i + len(group)}:\n" + "\n".join(lines))

    return "\n\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────
# [OPS:ING-001c] extract_table_chunks_from_xlsx_bytes()
#
# What it does: same idea as extract_text_from_xlsx_bytes(), but instead
# of flattening everything to plain text, it keeps each row-group as
# real structured data ({"text", "table": {sheet, columns, rows}}). The
# "table" part is what lets the frontend later draw an actual HTML table
# or chart from a cited chunk, instead of just quoting it as a wall of
# text.
#
# Called by: build_local_index.py / build_drive_index.py's
# discover_documents(), for any Excel file — feeds directly into
# make_table_chunk_documents().
# ─────────────────────────────────────────────────────────────────────────
def extract_table_chunks_from_xlsx_bytes(raw: bytes, rows_per_group: int = 12) -> List[Dict[str, Any]]:
    """
    Same row-grouping as extract_text_from_xlsx_bytes(), but returns each
    group as a {"text": ..., "table": {"sheet", "columns", "rows"}} chunk
    instead of a flattened blob — so the actual column/row data survives
    ingestion and can be rendered as a real table or chart later, not just
    read back as prose.
    """
    import pandas as pd

    sheets = pd.read_excel(io.BytesIO(raw), sheet_name=None, dtype=str)
    chunks: List[Dict[str, Any]] = []

    for sheet_name, df in sheets.items():
        df = df.dropna(how="all")
        if df.empty:
            continue
        columns = [str(c) for c in df.columns]
        records = df.fillna("").to_dict(orient="records")

        for i in range(0, len(records), rows_per_group):
            group = records[i : i + rows_per_group]
            lines = [
                f"Sheet '{sheet_name}': columns = {', '.join(columns)}. Rows {i + 1}-{i + len(group)} of {len(records)}."
            ]
            row_values: List[List[str]] = []
            for row in group:
                row_str = ", ".join(f"{k}={v}" for k, v in row.items() if str(v).strip())
                if row_str:
                    lines.append(row_str)
                row_values.append([str(row.get(c, "")) for c in columns])

            chunks.append(
                {
                    "text": "\n".join(lines),
                    "table": {"sheet": sheet_name, "columns": columns, "rows": row_values},
                }
            )

    return chunks


def extract_text_from_file(file_bytes: bytes, file_name: str) -> str:
    """Dispatch by file extension. Returns '' for unsupported types."""
    lower = file_name.lower()
    if lower.endswith(".pdf"):
        return extract_text_from_pdf_bytes(file_bytes)
    if lower.endswith(".docx"):
        return extract_text_from_docx_bytes(file_bytes)
    if lower.endswith((".xlsx", ".xlsm")):
        return extract_text_from_xlsx_bytes(file_bytes)
    if lower.endswith((".txt", ".md")):
        return file_bytes.decode("utf-8", errors="ignore")
    return ""


# ─────────────────────────────────────────────────────────────────────────
# [OPS:ING-001d] make_chunk_documents() / make_table_chunk_documents()
#
# What it does: builds the final document dict for each chunk — the
# shape everything downstream expects: {"id", "text", "metadata"}. The
# document's title is glued onto the front of every chunk's text, so
# even a chunk from deep in the middle of a long document still carries
# its title's context when it gets embedded. The metadata records which
# department it's from, whether it came from the local test folder or
# real Google Drive, and its position among the document's own chunks.
#
# Called by: build_local_index.py / build_drive_index.py's
# discover_documents() — the output feeds straight into
# PersistedInMemorySearch.ingest_documents().
# ─────────────────────────────────────────────────────────────────────────
def make_chunk_documents(
    text: str,
    *,
    id_prefix: str,
    file_name: str,
    title: str,
    department: str,
    owner_folder: str,
    source: str,
    extra_metadata: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    for i, chunk in enumerate(chunk_text(text)):
        metadata = {
            "source": source,
            "file_name": file_name,
            "title": title,
            "department": department,
            "owner_folder": owner_folder,
            "chunk_index": i,
        }
        if extra_metadata:
            metadata.update(extra_metadata)
        docs.append(
            {
                "id": f"{id_prefix}_{i}",
                "text": f"{title}\n\n{chunk}",
                "metadata": metadata,
            }
        )
    return docs


def make_table_chunk_documents(
    table_chunks: List[Dict[str, Any]],
    *,
    id_prefix: str,
    file_name: str,
    title: str,
    department: str,
    owner_folder: str,
    source: str,
    extra_metadata: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """
    Like make_chunk_documents(), but for pre-chunked Excel row-groups (from
    extract_table_chunks_from_xlsx_bytes) where the row/column boundaries are
    already the correct chunk boundaries — no generic paragraph re-chunking.
    """
    docs: List[Dict[str, Any]] = []
    for i, tc in enumerate(table_chunks):
        metadata = {
            "source": source,
            "file_name": file_name,
            "title": title,
            "department": department,
            "owner_folder": owner_folder,
            "chunk_index": i,
            "table": tc["table"],
        }
        if extra_metadata:
            metadata.update(extra_metadata)
        docs.append(
            {
                "id": f"{id_prefix}_{i}",
                "text": f"{title}\n\n{tc['text']}",
                "metadata": metadata,
            }
        )
    return docs


# ─────────────────────────────────────────────────────────────────────────
# [OPS:ING-001e] backup_index_if_exists()
#
# What it does: makes a timestamped copy of the search index file into a
# backups/ folder, right before something is about to delete and rebuild
# it. This exists so a bad or failed reindex can be recovered from
# instead of losing the whole search corpus. It only keeps the 5 most
# recent backups, deleting older ones automatically.
#
# Called by: every code path that deletes and rebuilds the index —
# build_local_index.py, build_drive_index.py, and discovery.py's
# _run_reindex() — right before it deletes the old file.
# ─────────────────────────────────────────────────────────────────────────
def backup_index_if_exists(index_path: Path, keep: int = 5) -> Path | None:
    """
    Versioned backup for enhanced_index.json, per the spec's "daily
    versioned backups" requirement — called right before any rebuild wipes
    the file (build_local_index.py --reset, build_drive_index.py --reset,
    and the admin-triggered /api/rag/admin/reindex endpoint all call this).

    Backups live in a sibling `backups/` folder, timestamped, with only the
    most recent `keep` retained. Returns the backup path, or None if there
    was nothing to back up.
    """
    index_path = Path(index_path)
    if not index_path.exists():
        return None

    backups_dir = index_path.parent / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backups_dir / f"{index_path.stem}.{stamp}{index_path.suffix}"
    shutil.copy2(index_path, backup_path)

    # Prune to the most recent `keep` backups for this index file.
    existing = sorted(backups_dir.glob(f"{index_path.stem}.*{index_path.suffix}"), key=lambda p: p.stat().st_mtime, reverse=True)
    for stale in existing[keep:]:
        stale.unlink(missing_ok=True)

    return backup_path
