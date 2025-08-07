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
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": exc.body,
        },
    )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
