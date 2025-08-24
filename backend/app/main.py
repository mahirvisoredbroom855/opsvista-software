<<<<<<< HEAD
<<<<<<< HEAD
# backend/app/main.py
from __future__ import annotations

import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import RedirectResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variable to store startup results
startup_results = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    
    # Startup
    logger.info("Starting OpsVista application...")
    
    try:
        # Simple chat system initialization - no Google Drive integration needed
        logger.info("Initializing RAG Chat System with enhanced index...")
        
        # Just verify the enhanced index exists
        index_paths = [
            "backend/app/features/rag_chatbot/vector/enhanced_index.json",
            "app/features/rag_chatbot/vector/enhanced_index.json"
        ]
        
        index_found = False
        for index_path in index_paths:
            if Path(index_path).exists():
                index_found = True
                logger.info(f"Enhanced index found: {index_path}")
                startup_results['chat_system'] = {
                    "status": "ready",
                    "message": f"Chat system ready with enhanced index at {index_path}",
                    "index_path": index_path
                }
                break
        
        if not index_found:
            logger.warning("Enhanced index not found - chat system will use fallback")
            startup_results['chat_system'] = {
                "status": "fallback",
                "message": "No enhanced index found, using fallback search",
                "suggestion": "Run gdrive_to_enhanced_index.py to create embeddings"
            }
            
    except Exception as e:
        logger.error(f"Chat system initialization failed: {e}")
        startup_results['chat_system'] = {"status": "failed", "error": str(e)}
    
    logger.info("Application startup completed")
    
    yield
    
    # Shutdown
    logger.info("Shutting down OpsVista application...")
    logger.info("Application shutdown completed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="OpsVista API",
        description="Business Intelligence System with RAG Chat",
        version="1.0.0",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan
    )
    
    # --- CORS (dev-friendly) ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify actual origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # --- Static files (/static/chat.html) ---
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        logger.info(f"Static files mounted from {static_dir}")
    
    # --- Include routers (NO extra prefix; routers carry their own) ---
    
    # Chat API: /api/rag/chat/_retrieve and /api/rag/chat/complete
    try:
        # When running from repo root: uvicorn backend.app.main:app
        from backend.app.features.rag_chatbot.api.chat import router as chat_router
        logger.info("Imported chat router from backend.app.features...")
    except ModuleNotFoundError:
        try:
            # When running from backend/: uvicorn app.main:app
            from app.features.rag_chatbot.api.chat import router as chat_router
            logger.info("Imported chat router from app.features...")
        except Exception as e:
            logger.error(f"Failed to import chat router: {e}")
            raise
    
    app.include_router(chat_router)
    logger.info("Chat router included")
    
    # Optional: Discovery API if present
    discovery_router = None
    try:
        from backend.app.features.rag_chatbot.api.discovery import router as disc_router
        discovery_router = disc_router
        logger.info("Imported discovery router from backend.app.features...")
    except ModuleNotFoundError:
        try:
            from app.features.rag_chatbot.api.discovery import router as disc_router
            discovery_router = disc_router
            logger.info("Imported discovery router from app.features...")
        except Exception as e:
            logger.warning(f"Discovery router not available: {e}")
            discovery_router = None
    
    if discovery_router:
        app.include_router(discovery_router)
        logger.info("Discovery router included")
    
    # --- Routes ---
    
    @app.get("/")
    async def root():
        """Root endpoint - redirect to chat UI if available."""
        # Redirect to the built-in chat UI if it exists; otherwise show a small message
        if static_dir.exists() and (static_dir / "chat.html").exists():
            return RedirectResponse(url="/static/chat.html")
        return {
            "ok": True,
            "message": "OpsVista API is running",
            "docs": "/docs",
            "chat_api": "/api/rag/chat/complete",
            "status": "/api/status"
        }
    
    @app.get("/healthz")
    async def healthz():
        """Health check endpoint."""
        return {"ok": True, "status": "healthy"}
    
    @app.get("/api/status")
    async def api_status():
        """Comprehensive API status."""
        try:
            # Get chat system status
            chat_status = startup_results.get('chat_system', {"status": "unknown"})
            
            # Check enhanced index status
            index_status = None
            index_paths = [
                "backend/app/features/rag_chatbot/vector/enhanced_index.json",
                "app/features/rag_chatbot/vector/enhanced_index.json"
            ]
            
            for index_path in index_paths:
                if Path(index_path).exists():
                    index_file = Path(index_path)
                    index_status = {
                        "path": index_path,
                        "exists": True,
                        "size_mb": round(index_file.stat().st_size / 1024 / 1024, 2),
                        "modified": index_file.stat().st_mtime
                    }
                    break
            
            if not index_status:
                index_status = {"exists": False, "message": "Enhanced index not found"}
            
            return {
                "api_status": "operational",
                "timestamp": "2025-08-22",
                "chat_system": chat_status,
                "enhanced_index": index_status,
                "available_endpoints": {
                    "chat": "/api/rag/chat/complete",
                    "retrieve": "/api/rag/chat/_retrieve", 
                    "docs": "/docs"
                }
            }
            
        except Exception as e:
            logger.error(f"Status check failed: {e}")
            return {
                "api_status": "degraded",
                "error": str(e),
                "chat_system": startup_results.get('chat_system', {"status": "unknown"})
            }
    
    return app


# Create the FastAPI app instance
app = create_app()


# Additional configuration for development
if __name__ == "__main__":
    import uvicorn
    
    # Development server configuration
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
=======
# Main FastAPI Application with Background Tasks
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import os
from dotenv import load_dotenv
import logging

# Load environment variables
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import routers and services
from app.features.finance.router import router as finance_router
from app.features.finance.websocket import create_socketio_app, sio

# Create FastAPI app
app = FastAPI(
    title="OpsVista Finance API",
    version="1.0.0",
    description="Automated Finance Processing System with Real-time Background Tasks"
)

# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error: {exc.errors()}")
=======
# backend/app/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import traceback


# ⬇️  existing feature routers
from app.features.task_assignment.api.v1.tasks import router as task_router

# ⬇️  NEW – logout /auth endpoints ---------------------------
from app.features.task_assignment.api.v1.sessions import router as auth_router
# ------------------------------------------------------------

app = FastAPI(title="OpsVista API", version="0.1.0")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print("❌ Validation error:")
    traceback.print_exc()
    print("Body received:", exc.body)
    print("Validation details:", exc.errors())
>>>>>>> origin/feat/task-assignment
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": exc.body,
        },
    )

<<<<<<< HEAD
# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
=======


# (optional) CORS — keep if you already have it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
>>>>>>> origin/feat/task-assignment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

<<<<<<< HEAD
# Include routers
app.include_router(finance_router)

# Health check endpoints
@app.get("/")
async def root():
    return {
        "message": "OpsVista Finance API",
        "version": "1.0.0",
        "features": [
            "Automated Excel Processing",
            "Real-time Background Tasks",
            "WebSocket Updates",
            "Google Drive Integration"
        ]
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": "2025-01-28T12:00:00Z",
        "services": {
            "api": "online",
            "background_tasks": "running",
            "websocket": "available"
        }
    }

# Background task management endpoints
@app.get("/api/v1/system/tasks/status")
async def get_task_status():
    """Get background task system status"""
    try:
        from app.core.celery_app import celery_app
        
        # Check Celery status
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        active_tasks = inspect.active()
        
        return {
            "status": "online" if stats else "offline",
            "workers": len(stats) if stats else 0,
            "active_tasks": sum(len(tasks) for tasks in active_tasks.values()) if active_tasks else 0,
            "queues": ["finance"],
            "schedule": {
                "sync_interval": "3 minutes",
                "cleanup_time": "2:00 AM daily"
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@app.post("/api/v1/system/tasks/trigger-sync")
async def trigger_manual_sync():
    """Manually trigger finance sync"""
    try:
        from app.features.finance.tasks import scheduled_finance_sync
        
        # Queue the sync task
        task = scheduled_finance_sync.delay()
        
        return {
            "status": "queued",
            "task_id": task.id,
            "message": "Manual sync triggered successfully"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

# Create the complete app with Socket.IO
socketio_app = create_socketio_app(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:socketio_app", host="0.0.0.0", port=8000, reload=True)
>>>>>>> origin/feat/finances-dashboard
=======
# ⬇️  include all routers
app.include_router(task_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")   # 🚀 now /api/v1/auth/logout works




>>>>>>> origin/feat/task-assignment
