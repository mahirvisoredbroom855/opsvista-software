from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(
    title="OpsVista Finance API", 
    version="1.0.0",
    description="Finance Automation System"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "message": "OpsVista Finance API",
        "version": "1.0.0", 
        "status": "running",
        "redis_connected": True
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "timestamp": "2025-01-28T12:00:00Z",
        "services": {
            "api": "online",
            "redis": "connected"
        }
    }

# Mock endpoints for testing
@app.get("/api/v1/finance/dashboard/metrics")
def get_dashboard_metrics():
    return {
        "today_cash_received": 125000.50,
        "month_cash_received": 2750000.75,
        "year_profit_loss": 450000.25,
        "total_transactions": 1234,
        "processing_files": 0,
        "last_update": "2025-01-28T12:00:00Z"
    }

@app.get("/api/v1/system/tasks/status")
def get_task_status():
    return {
        "status": "online",
        "workers": 2,
        "active_tasks": 0,
        "redis_connected": True
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
