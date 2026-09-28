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

# ═══════════════════════════════════════════════════════════════════════
# MODULE: [OPS:ADMIN-001] — admin-triggered reindex API
#
# The one endpoint the scheduled-reindex.yml GitHub Action [OPS:CI-001]
# calls at 03:00 UTC daily, plus the same logic reachable manually from
# the dashboard. Runs the SAME discovery/ingestion code path as the CLI
# script build_drive_index.py — deliberately not a separate reimplemen-
# tation — so "run it from cron" and "run it from the CLI" can never
# silently drift apart in behavior.
# ═══════════════════════════════════════════════════════════════════════
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
# [OPS:ADMIN-001a] _run_reindex() — the full pipeline: Drive scan → chunk →
#                 embed → rebuild JSON index → dual-write pgvector
#
# API/CALL: Google Drive API (via GoogleDriveService [OPS:DRIVE-001]),
#       Gemini embed_content (via [OPS:IDX-002] embed_texts(), inside
#       PersistedInMemorySearch.ingest_documents() [OPS:IDX-004]),
#       Supabase REST (via [OPS:PVEC-003] upsert_documents()).
# CALLS: discover_documents() (build_drive_index.py [OPS:DRIVE-003]),
#       backup_index_if_exists() [OPS:ING-001e], PersistedInMemorySearch
#       [OPS:IDX-003]/[OPS:IDX-004], upsert_documents() [OPS:PVEC-003].
# WHY FULL REBUILD, NOT INCREMENTAL: the JSON index has no dedup/upsert
#       logic on append — ingest_documents() always appends — so a
#       repeated incremental reindex would accumulate duplicate chunks
#       over time. Deleting and rebuilding from scratch (matching
#       build_drive_index.py --reset) is what keeps it correct;
#       pgvector's side is safe either way since it upserts on a real
#       conflict key (document_id, ordinal).
# RUNS AS: a background task (threading, not asyncio) — a full Drive
#       scan + re-embed can take minutes, so this can't block the HTTP
#       response; _reindex_lock + _reindex_state give the polling
#       GET /reindex/status endpoint something to read concurrently.
# CALLED BY: [OPS:ADMIN-001b] trigger_reindex() via
#       BackgroundTasks.add_task(); also invoked identically by the CI
#       cron job hitting POST /reindex — same code, same guarantees.
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
# [OPS:ADMIN-001b] POST /reindex — kicks off _run_reindex() as a
#                 background task; returns immediately with "started"
#
# RATE LIMIT: 3/minute — deliberately much stricter than chat endpoints,
#       since a reindex is an expensive Drive scan + full re-embedding
#       run, not a cheap per-request operation. The 409 "already in
#       progress" guard (via _reindex_state) is the real protection
#       against overlapping runs; the rate limit is a secondary guard
#       against accidental rapid-fire triggering.
# AUTH: [OPS:AUTH-005] — Owner/Admin session OR X-Automation-Token.
# CALLED BY (over HTTP): the dashboard's manual "Reindex now" action;
#       scheduled-reindex.yml's [OPS:CI-001] daily cron, using
#       X-Automation-Token instead of a session.
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


# [OPS:ADMIN-001c] GET /reindex/status — polled by the dashboard and by
# scheduled-reindex.yml's [OPS:CI-001] status-check step after triggering
# a reindex, since the actual work runs in a background thread.
@router.get("/reindex/status")
def reindex_status(current_user: Dict[str, Any] = Depends(_require_admin)) -> Dict[str, Any]:
    return _reindex_state
