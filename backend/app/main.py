# backend/app/main.py
"""
This is the file that starts the whole backend. When the server boots,
this is what runs first: it checks whether the search index already
exists on disk, and if not, rebuilds it from the Supabase database so
the app never starts up empty-handed. It then assembles the actual web
server — wiring up who's allowed to call it from a browser (CORS),
how many requests per minute each visitor gets (rate limiting), and
which URL paths lead to which feature (the chat, admin, and status
routes). Nothing in the app is reachable over the internet until this
file has run.
"""
# ─────────────────────────────────────────────────────────────────────────
# MODULE: [OPS:MAIN]
#
# What it does: builds the FastAPI app (create_app()) and defines what
# runs before the server accepts its first request (lifespan()) — check
# for a local search index, rebuild it from Supabase if it's missing.
# ─────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import RedirectResponse

from app.core.rate_limit import limiter

# Load repo-root .env into os.environ before anything else. Several modules
# (persisted_inmemory_search.py, llm_client.py) read OPENAI_API_KEY /
# GEMINI_API_KEY / USE_MOCK_EMBEDDINGS via os.getenv() directly rather than
# through app.core.config's pydantic Settings, so without this they'd never
# see values from .env at all.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("opsvista.main")

# -----------------------------------------------------------------------------
# Globals
# -----------------------------------------------------------------------------
startup_results: dict = {}

# Resolve important paths relative to this file so both run modes work:
# - repo root:   uvicorn --app-dir backend app.main:app
# - backend/:    uvicorn app.main:app
HERE = Path(__file__).parent
VECTOR_DIR = HERE / "features" / "rag_chatbot" / "vector"
STATIC_DIR = HERE / "static"

# Fallbacks if someone runs from a different cwd
ALT_VECTOR_JSON = Path("backend/app/features/rag_chatbot/vector/enhanced_index.json")

ENHANCED_INDEX_CANDIDATES = [
    VECTOR_DIR / "enhanced_index.json",
    ALT_VECTOR_JSON,
]

def _find_enhanced_index() -> Path | None:
    for p in ENHANCED_INDEX_CANDIDATES:
        try:
            if p.exists():
                return p
        except Exception:
            continue
    return None

def _cors_origins_from_env() -> list[str]:
    """
    CORS_ALLOWED_ORIGINS="https://your-frontend.vercel.app,https://example.com"
    If not set, default to ["*"] for dev; tighten in prod.
    """
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    if not raw:
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]

# -----------------------------------------------------------------------------
# Lifespan
# -----------------------------------------------------------------------------
# ─────────────────────────────────────────────────────────────────────────
# [OPS:MAIN-002] lifespan()
#
# What it does: runs once at server startup, before any request is
# accepted. First it looks for the search index file on local disk. If
# it's there, done. If it's not, it calls Supabase to pull the same data
# back down and rebuilds the file from that. This matters because on
# Render's free hosting tier, local disk is wiped on every restart —
# without this step, every restart would silently boot with an empty
# search index until someone manually reindexed. Confirmed by testing:
# deleting the local index and restarting rebuilt it automatically from
# Supabase.
#
# Called by: FastAPI itself, automatically, once at process startup.
# ─────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting OpsVista application…")
    try:
        idx = _find_enhanced_index()
        if idx:
            startup_results["chat_system"] = {
                "status": "ready",
                "message": f"Enhanced index found",
                "index_path": str(idx),
            }
            logger.info("Enhanced index located at %s", idx)
        else:
            # Local disk is ephemeral on platforms like Render — a restart or
            # redeploy wipes enhanced_index.json even though the same data is
            # already sitting in Supabase (dual-written at ingest time).
            # Rehydrate from there instead of booting with an empty index.
            logger.warning("Enhanced index not found locally; attempting to hydrate from Supabase…")
            hydrated = None
            try:
                from app.features.rag_chatbot.vector.pgvector_store import hydrate_index_from_supabase

                hydrated = hydrate_index_from_supabase()
            except Exception:
                logger.exception("Hydration from Supabase failed")

            if hydrated:
                target = VECTOR_DIR / "enhanced_index.json"
                target.parent.mkdir(parents=True, exist_ok=True)
                with open(target, "w", encoding="utf-8") as f:
                    json.dump(hydrated, f)
                startup_results["chat_system"] = {
                    "status": "ready",
                    "message": f"Rehydrated enhanced index from Supabase ({len(hydrated['items'])} chunks)",
                    "index_path": str(target),
                }
                logger.info("Rehydrated enhanced index from Supabase: %d chunks at %s", len(hydrated["items"]), target)
            else:
                startup_results["chat_system"] = {
                    "status": "fallback",
                    "message": "No enhanced index found, using fallback search",
                    "suggestion": "Run gdrive_to_enhanced_index.py to create embeddings",
                }
                logger.warning("Enhanced index not found and Supabase hydration unavailable; starting in fallback mode")
    except Exception as e:
        logger.exception("Chat system initialization failed")
        startup_results["chat_system"] = {"status": "failed", "error": str(e)}

    logger.info("Application startup completed")
    yield
    logger.info("Shutting down OpsVista application…")
    logger.info("Application shutdown completed")

# -----------------------------------------------------------------------------
# App factory
# -----------------------------------------------------------------------------
# [OPS:MAIN-003] create_app()
#
# What it does: builds the actual FastAPI application object, step by
# step — turns on rate limiting, turns on CORS (so the frontend on
# Vercel is allowed to call this API from a browser), then attaches each
# feature's routes (chat, admin metrics, discovery) one at a time, and
# finally adds a couple of plain health-check routes. Returns the
# finished app object.
#
# Called by: this file itself, once, to build the `app` variable that
# uvicorn actually runs.
def create_app() -> FastAPI:
    app = FastAPI(
        title="OpsVista API",
        description="Business Intelligence System with RAG Chat",
        version="1.0.0",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    # --- Rate limiting (per-IP; see app/core/rate_limit.py for the shared instance) ---
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # --- CORS ---
    allow_origins = _cors_origins_from_env()

    explicit = os.getenv("CORS_ALLOWED_ORIGINS", "")
    allow_list = [o.strip() for o in explicit.split(",") if o.strip()]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_list,                 # explicit origins from env
        allow_origin_regex=r"https://.*\.vercel\.app$",  # allow all Vercel previews + prod
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],  
    )
    logger.info("CORS allow_origins=%s", allow_origins)

    # --- Static files ---
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
        logger.info("Static files mounted from %s", STATIC_DIR)

    # --- Routers ---
    # Try imports for both run modes. We prefer 'app.' path since tests do:
    # from app.main import app
    try:
        from app.features.rag_chatbot.api.chat import router as chat_router
        logger.info("Imported chat router from app.features…")
    except ModuleNotFoundError:
        # Some run from repo root with different sys.path setups
        from backend.app.features.rag_chatbot.api.chat import router as chat_router
        logger.info("Imported chat router from backend.app.features…")

    app.include_router(chat_router)
    logger.info("Chat router included at /api/rag/chat/*")

    # Admin metrics router (observability dashboard backend)
    try:
        from app.features.rag_chatbot.api.admin_metrics import router as admin_metrics_router
        app.include_router(admin_metrics_router)
        logger.info("Admin metrics router included at /api/rag/admin/*")
    except ModuleNotFoundError:
        try:
            from backend.app.features.rag_chatbot.api.admin_metrics import router as admin_metrics_router  # type: ignore
            app.include_router(admin_metrics_router)
            logger.info("Admin metrics router included (backend.* path)")
        except Exception as e:
            logger.info("Admin metrics router not available: %s", e)

    # Optional discovery router
    try:
        from app.features.rag_chatbot.api.discovery import router as discovery_router
        app.include_router(discovery_router)
        logger.info("Discovery router included")
    except ModuleNotFoundError:
        try:
            from backend.app.features.rag_chatbot.api.discovery import router as discovery_router  # type: ignore
            app.include_router(discovery_router)
            logger.info("Discovery router included (backend.* path)")
        except Exception as e:
            logger.info("Discovery router not available: %s", e)

    # --- Convenience routes ---
    @app.get("/")
    async def root():
        """Redirect to chat UI if available, otherwise show a small message."""
        if STATIC_DIR.exists() and (STATIC_DIR / "chat.html").exists():
            return RedirectResponse(url="/static/chat.html")
        return {
            "ok": True,
            "message": "OpsVista API is running",
            "docs": "/docs",
            "chat_api": "/api/rag/chat/complete",
            "status": "/api/status",
        }

    @app.get("/healthz")
    async def healthz():
        return {"ok": True, "status": "healthy"}

    @app.get("/api/status")
    async def api_status():
        """Aggregate status without calling external services."""
        try:
            idx = _find_enhanced_index()
            index_status = (
                {
                    "path": str(idx),
                    "exists": True,
                    "size_mb": round(idx.stat().st_size / 1024 / 1024, 2),
                    "modified_epoch": idx.stat().st_mtime,
                }
                if idx
                else {"exists": False, "message": "Enhanced index not found"}
            )

            return {
                "api_status": "operational",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "chat_system": startup_results.get("chat_system", {"status": "unknown"}),
                "enhanced_index": index_status,
                "available_endpoints": {
                    "chat_complete": "/api/rag/chat/complete",
                    "chat_retrieve": "/api/rag/chat/_retrieve",
                    "chat_status": "/api/rag/chat/status",
                    "docs": "/docs",
                },
            }
        except Exception as e:
            logger.exception("Status check failed")
            return {
                "api_status": "degraded",
                "error": str(e),
                "chat_system": startup_results.get("chat_system", {"status": "unknown"}),
            }

    return app

# Public ASGI app
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",  # run from backend/: python -m uvicorn app.main:app --reload
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
