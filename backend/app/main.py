from __future__ import annotations
import os, logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("opsvista")

app = FastAPI(title="OpsVista Backend", version="0.1.0")

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN, "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _try_include_any(import_paths: list[str], attr: str = "router", prefix: str = "", tags: list[str] | None = None):
    for import_path in import_paths:
        try:
            mod = __import__(import_path, fromlist=[attr])
            router = getattr(mod, attr, None)
            if router is None:
                log.warning("Module %s has no attribute '%s'", import_path, attr)
                continue
            app.include_router(router, prefix=prefix, tags=tags)
            log.info("Mounted %s at %s", import_path, prefix or "/")
            return
        except Exception as e:
            log.warning("Skipping %s: %s", import_path, e)

# Finance
_try_include_any(
    ["app.features.finance.router", "backend.app.features.finance.router"],
    attr="router", prefix="/api/finance", tags=["finance"]
)

# RAG Chatbot
_try_include_any(
    ["app.features.rag_chatbot.api.chat", "backend.app.features.rag_chatbot.api.chat"],
    attr="router", prefix="/api/chat", tags=["rag-chat"]
)
_try_include_any(
    ["app.features.rag_chatbot.api.discovery", "backend.app.features.rag_chatbot.api.discovery"],
    attr="router", prefix="/api/rag/discovery", tags=["rag-discovery"]
)
_try_include_any(
    ["app.features.rag_chatbot.api.chat_gdrive_integration", "backend.app.features.rag_chatbot.api.chat_gdrive_integration"],
    attr="router", prefix="/api/rag/gdrive", tags=["rag-gdrive"]
)

# Tasks
_try_include_any(
    ["app.features.task_assignment.api.v1.tasks", "backend.app.features.task_assignment.api.v1.tasks"],
    attr="router", prefix="/api/v1/tasks", tags=["tasks"]
)
_try_include_any(
    ["app.features.task_assignment.api.v1.sessions", "backend.app.features.task_assignment.api.v1.sessions"],
    attr="router", prefix="/api/v1/sessions", tags=["auth"]
)

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    log.info("Mounted static at /static")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def root():
    return {
        "app": "OpsVista Backend",
        "version": "0.1.0",
        "endpoints": [
            "/health",
            "/api/finance",
            "/api/chat",
            "/api/rag/discovery",
            "/api/rag/gdrive",
            "/api/v1/tasks",
            "/api/v1/sessions",
            "/static/chat.html",
        ],
        "frontend_origin": FRONTEND_ORIGIN,
    }
