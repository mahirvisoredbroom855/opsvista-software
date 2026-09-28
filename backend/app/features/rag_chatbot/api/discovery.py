# backend/app/features/rag_chatbot/api/discovery.py
"""
This file is what re-reads every document in Google Drive and rebuilds
OpsVista's entire search index from scratch — triggered either by an
Owner/Admin clicking "Reindex now" on the dashboard, or automatically
every night by a scheduled job. It runs in the background, since
scanning and re-processing every document can take a few minutes, and
a separate status check lets the dashboard show progress while it works.

Admin-triggered reindex API.

Replaces prior scaffolding that referenced a `rag_system.document_inventory`
table and DocumentTypeClassifier/analyzer classes that were never actually
wired up correctly (it imported PyPDF2, which isn't even a project
dependency — pypdf is). None of that matched the schema this project
actually uses (dim_document/fact_chunk/fact_embedding, see
backend/sql/schema.sql).

This calls directly into the same discovery/ingestion logic used by
build_drive_index.py — the one pipeline that's actually verified working —
so the CLI script and the admin API produce identical, consistent results.

Runs as a background task since a full reindex (Drive scan + re-embedding)
can take a while; poll GET /api/rag/admin/reindex/status for progress.
"""
from __future__ import annotations

import logging
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from app.core.auth_deps import require_roles_or_automation_token
from app.core.rate_limit import limiter

# ─────────────────────────────────────────────────────────────────────────
# MODULE: [OPS:ADMIN-001]
#
# What it does: rebuilds the entire search index from Google Drive from
# scratch. It reuses the exact same scan/chunk/embed code as the
# build_drive_index.py CLI script, rather than a separate copy of that
# logic, so the nightly cron job and a manual "Reindex now" click always
# behave identically.
# ─────────────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/rag/admin", tags=["Admin Reindex"])
logger = logging.getLogger(__name__)

# [OPS:AUTH-005] — accepts either an Owner/Admin Supabase session OR the
# X-Automation-Token header, since the cron job has no user session.
_require_admin = require_roles_or_automation_token(["Owner", "Admin"])

# backend/app/features/rag_chatbot/api/discovery.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parents[4]

_reindex_lock = threading.Lock()
_reindex_state: Dict[str, Any] = {
    "status": "idle",  # idle | running | completed | failed
    "started_at": None,
    "finished_at": None,
    "result": None,
    "error": None,
}


# ─────────────────────────────────────────────────────────────────────────
# [OPS:ADMIN-001a] _run_reindex()
#
# What it does: the actual reindex pipeline. Connects to Google Drive,
# lists every document in the tracked folders, deletes the old local
# index file, rebuilds it from scratch (chunking and embedding every
# document again), and pushes the same data to Supabase. It always
# rebuilds from zero rather than adding incrementally, because the local
# index file has no way to detect and skip a duplicate chunk — adding
# incrementally would slowly fill it with repeats.
#
# Runs on a background thread (not the request thread) because a full
# Drive scan and re-embed can take several minutes — it updates a shared
# `_reindex_state` dict as it goes, which the status endpoint reads.
#
# Called by: trigger_reindex(), as a background task — both the
# dashboard's manual button and the nightly cron job go through it.
# ─────────────────────────────────────────────────────────────────────────
def _run_reindex(folder_names: Optional[List[str]] = None) -> None:
    with _reindex_lock:
        _reindex_state.update(
            {"status": "running", "started_at": datetime.now(timezone.utc).isoformat(), "finished_at": None, "error": None, "result": None}
        )

    try:
        if str(BACKEND_DIR) not in sys.path:
            sys.path.insert(0, str(BACKEND_DIR))
        # Imported lazily (not at module load time) so a missing Drive
        # credentials file or bad import never blocks the whole API from
        # starting — same principle as this file's own bug we're fixing.
        from build_drive_index import FOLDER_DEPARTMENT_MAP, discover_documents

        from app.features.rag_chatbot.ingestion_common import backup_index_if_exists
        from app.features.rag_chatbot.vector.google_drive_service import GoogleDriveService
        from app.features.rag_chatbot.vector.persisted_inmemory_search import PersistedInMemorySearch
        from app.features.rag_chatbot.vector.pgvector_store import is_configured, upsert_documents

        drive = GoogleDriveService()
        conn_status = drive.test_connection()
        if not conn_status.get("connected"):
            raise RuntimeError(f"Google Drive connection failed: {conn_status.get('error')}")

        names = folder_names or list(FOLDER_DEPARTMENT_MAP.keys())
        documents = discover_documents(drive, names)
        if not documents:
            raise RuntimeError("No documents discovered — check folder sharing with the service account")

        # Full rebuild (matches build_drive_index.py --reset): the JSON index
        # has no dedup/upsert logic on append, so repeated incremental
        # ingests would drift with duplicates. pgvector's side uses
        # on_conflict upserts and is safe either way.
        index_path = BACKEND_DIR / "app/features/rag_chatbot/vector/enhanced_index.json"
        if index_path.exists():
            backup_index_if_exists(index_path)
            index_path.unlink()

        index = PersistedInMemorySearch(index_path=index_path)
        index.ingest_documents(documents)

        pg_stats: Dict[str, Any] = {}
        if is_configured():
            pg_stats = upsert_documents(index.items)

        with _reindex_lock:
            _reindex_state.update(
                {
                    "status": "completed",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "result": {
                        "chunks_discovered": len(documents),
                        "index_stats": index.get_stats(),
                        "pgvector": pg_stats,
                    },
                }
            )
    except Exception as e:
        logger.exception("Reindex failed")
        with _reindex_lock:
            _reindex_state.update({"status": "failed", "finished_at": datetime.now(timezone.utc).isoformat(), "error": str(e)})


# ─────────────────────────────────────────────────────────────────────────
# [OPS:ADMIN-001b] POST /reindex
#
# What it does: starts _run_reindex() running in the background and
# replies immediately with "started" — it doesn't wait for the reindex
# to finish. If a reindex is already running, it replies with an error
# (409) instead of starting a second one at the same time. Accepts
# either a logged-in Owner/Admin, or the automation token the nightly
# cron job uses instead. Limited to 3 requests/minute, since a reindex
# is an expensive operation, not something meant to be triggered rapidly.
#
# Called by: the dashboard's "Reindex now" button, and the nightly
# GitHub Action.
# ─────────────────────────────────────────────────────────────────────────
@router.post("/reindex")
@limiter.limit("3/minute")
def trigger_reindex(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(_require_admin),
) -> Dict[str, Any]:
    """Trigger a full Drive re-scan + re-embed + dual-write. Requires Owner/Admin role."""
    if _reindex_state["status"] == "running":
        raise HTTPException(status_code=409, detail="Reindex already in progress")
    background_tasks.add_task(_run_reindex)
    return {"status": "started", "message": "Reindex running in background; poll GET /api/rag/admin/reindex/status"}


# [OPS:ADMIN-001c] GET /reindex/status
#
# What it does: just returns the current state dict — whether a reindex
# is idle, running, completed, or failed, and its result once done.
# Exists because the actual reindex runs in the background, so the
# caller has to poll this to find out when it's finished.
#
# Called by: the dashboard (while showing a "reindexing..." spinner) and
# the nightly GitHub Action, right after it triggers a reindex.
@router.get("/reindex/status")
def reindex_status(current_user: Dict[str, Any] = Depends(_require_admin)) -> Dict[str, Any]:
    return _reindex_state
