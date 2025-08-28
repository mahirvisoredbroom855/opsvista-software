# backend/app/main.py
from __future__ import annotations

import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import RedirectResponse

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
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting OpsVista application…")
    try:
        # Minimal, non-failing startup checks (no external calls)
        idx = _find_enhanced_index()
        if idx:
            startup_results["chat_system"] = {
                "status": "ready",
                "message": f"Enhanced index found",
                "index_path": str(idx),
            }
            logger.info("Enhanced index located at %s", idx)
        else:
            startup_results["chat_system"] = {
                "status": "fallback",
                "message": "No enhanced index found, using fallback search",
                "suggestion": "Run gdrive_to_enhanced_index.py to create embeddings",
            }
            logger.warning("Enhanced index not found; starting in fallback mode")
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
def create_app() -> FastAPI:
    app = FastAPI(
        title="OpsVista API",
        description="Business Intelligence System with RAG Chat",
        version="1.0.0",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    # --- CORS ---
    allow_origins = _cors_origins_from_env()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
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
