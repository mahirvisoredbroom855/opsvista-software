from __future__ import annotations
import os, logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware


# Load environment variables FIRST, before any imports that might depend on them
try:
    from dotenv import load_dotenv
    # Load .env from the current directory (backend)
    load_dotenv()
    # Also try loading from parent directory (repo root)
    load_dotenv(Path(__file__).parent.parent / ".env")
except Exception as e:
    print(f"Warning: Could not load .env file: {e}")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("opsvista")

app = FastAPI(title="OpsVista Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get CORS origins from environment
cors_origins = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173").split(",")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[*cors_origins, FRONTEND_ORIGIN, "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _check_env_vars():
    """Check if required environment variables are set"""
    required_vars = {
        "SUPABASE_JWT_SECRET": os.getenv("SUPABASE_JWT_SECRET"),
        "SUPABASE_URL": os.getenv("SUPABASE_URL"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    }
    
    for var_name, var_value in required_vars.items():
        if var_value:
            log.info(f"✅ {var_name} is set")
        else:
            log.warning(f"❌ {var_name} is not set")

# Check environment variables on startup
_check_env_vars()

def _try_include_any(import_paths: list[str], attr: str = "router", prefix: str = "", tags: list[str] | None = None):
    for import_path in import_paths:
        try:
            mod = __import__(import_path, fromlist=[attr])
            router = getattr(mod, attr, None)
            if router is None:
                log.warning("Module %s has no attribute '%s'", import_path, attr)
                continue
            app.include_router(router, prefix=prefix, tags=tags)
            log.info("✅ Mounted %s at %s", import_path, prefix or "/")
            return
        except ImportError as e:
            log.warning("❌ Import error for %s: %s", import_path, e)
        except Exception as e:
            log.warning("❌ Skipping %s: %s", import_path, e)

# Finance - check for API key first
if os.getenv("OPENAI_API_KEY"):
    _try_include_any(
        ["app.features.finance.router"],
        attr="router", prefix="/api/finance", tags=["finance"]
    )
else:
    log.warning("❌ Skipping finance router: OPENAI_API_KEY not set")

# RAG Chatbot
_try_include_any(
    ["app.features.rag_chatbot.api.chat"],
    attr="router", prefix="/api/chat", tags=["rag-chat"]
)

# RAG Discovery - check for JWT secret
if os.getenv("SUPABASE_JWT_SECRET"):
    _try_include_any(
        ["app.features.rag_chatbot.api.discovery"],
        attr="router", prefix="/api/rag/discovery", tags=["rag-discovery"]
    )
else:
    log.warning("❌ Skipping RAG discovery: SUPABASE_JWT_SECRET not set")

# RAG GDrive integration
_try_include_any(
    ["app.features.rag_chatbot.api.chat_gdrive_integration"],
    attr="router", prefix="/api/rag/gdrive", tags=["rag-gdrive"]
)

# Tasks - check for JWT secret
if os.getenv("SUPABASE_JWT_SECRET"):
    _try_include_any(
        ["app.features.task_assignment.api.v1.tasks"],
        attr="router", prefix="/api/v1/tasks", tags=["tasks"]
    )
    _try_include_any(
        ["app.features.task_assignment.api.v1.sessions"],
        attr="router", prefix="/api/v1/sessions", tags=["auth"]
    )
else:
    log.warning("❌ Skipping task routes: SUPABASE_JWT_SECRET not set")

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    log.info("✅ Mounted static at /static")

@app.get("/health")
def health():
    return {"status": "ok", "environment": {
        "SUPABASE_JWT_SECRET": "✅" if os.getenv("SUPABASE_JWT_SECRET") else "❌",
        "SUPABASE_URL": "✅" if os.getenv("SUPABASE_URL") else "❌", 
        "OPENAI_API_KEY": "✅" if os.getenv("OPENAI_API_KEY") else "❌",
    }}

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