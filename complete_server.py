from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import List, Dict, Any
import redis
import json
import random
import uuid
import uvicorn

app = FastAPI(
    title="OpsVista Finance API", 
    version="1.0.0",
    description="Complete Finance Automation System with Mock Data"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis connection for background tasks
try:
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    redis_connected = redis_client.ping()
except:
    redis_connected = False

# Mock data generators
def generate_mock_transactions(count: int = 10):
    """Generate mock transaction data"""
    transaction_types = ['cash_received', 'cash_paid', 'bank_transfer', 'expense']
    parties = ['Rojina Enterprise', 'Dhaka Suppliers', 'Local Vendor', 'Cash Customer']
    
    transactions = []
    for i in range(count):
        transactions.append({
            'id': str(uuid.uuid4()),
            'date': (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat(),
            'type': random.choice(transaction_types),
            'amount': round(random.uniform(1000, 50000), 2),
            'party_name': random.choice(parties),
            'description': f'Transaction {i+1} - Business payment',
            'status': 'completed'
        })
    
    return transactions

def generate_mock_processing_files():
    """Generate mock file processing data"""
    files = [
        {
            'id': str(uuid.uuid4()),
            'source_file': '1.Cash Book_2025.xlsx',
            'file_type': 'cash_book', 
            'status': 'completed',
            'created_at': (datetime.now() - timedelta(hours=2)).isoformat(),
            'processing_started': (datetime.now() - timedelta(hours=2)).isoformat(),
            'processing_completed': (datetime.now() - timedelta(hours=1, minutes=55)).isoformat(),
            'rows_processed': 337,
            'rows_successful': 297,
            'rows_failed': 40
        },
        {
            'id': str(uuid.uuid4()),
            'source_file': 'Cash Party Due Bill_2024-2025.xlsx', 
            'file_type': 'party_due_bill',
            'status': 'processing',
            'created_at': (datetime.now() - timedelta(minutes=15)).isoformat(),
            'processing_started': (datetime.now() - timedelta(minutes=15)).isoformat(),
            'processing_completed': None,
            'rows_processed': 156,
            'rows_successful': 140,
            'rows_failed': 5
        }
    ]
    return files

# =====================================
# CORE API ENDPOINTS
# =====================================

@app.get("/")
def root():
    return {
        "message": "OpsVista Finance API",
        "version": "1.0.0", 
        "status": "running",
        "redis_connected": redis_connected,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "api": "online",
            "redis": "connected" if redis_connected else "disconnected",
            "background_tasks": "running"
        }
    }

# =====================================
# FINANCE ENDPOINTS 
# =====================================

@app.get("/api/v1/finance/health")
def finance_health():
    """Database connection health check"""
    return {
        "database_connection": True,  # Mock - always true for now
        "last_transaction": datetime.now().isoformat(),
        "total_records": 15847,
        "status": "healthy"
    }

@app.get("/api/v1/finance/dashboard/metrics")
def get_dashboard_metrics():
    """Get real-time dashboard metrics"""
    return {
        "today_cash_received": 125000.50,
        "month_cash_received": 2750000.75,
        "year_revenue": 15500000.00,
        "year_profit_loss": 2450000.25,
        "total_transactions": 15847,
        "processing_files": 1,
        "last_sync": datetime.now().isoformat(),
        "data_quality_score": 0.94,
        "system_status": "operational"
    }

@app.get("/api/v1/finance/transactions")
def get_transactions(
    limit: int = 50,
    offset: int = 0,
    date_from: str = None,
    date_to: str = None
):
    """Get paginated transactions"""
    transactions = generate_mock_transactions(limit)
    
    return {
        "transactions": transactions,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": 15847,
            "has_more": True
        },
        "filters_applied": {
            "date_from": date_from,
            "date_to": date_to
        }
    }

@app.get("/api/v1/finance/files/processing")
def get_file_processing_status():
    """Get file processing status"""
    return generate_mock_processing_files()

# =====================================
# SYSTEM TASK ENDPOINTS
# =====================================

@app.get("/api/v1/system/tasks/status")
def get_task_status():
    """Get background task system status"""
    return {
        "status": "online",
        "workers": 2,
        "active_tasks": random.randint(0, 3),
        "completed_tasks_today": 24,
        "failed_tasks_today": 1,
        "queues": ["finance", "notifications"],
        "redis_connected": redis_connected,
        "last_heartbeat": datetime.now().isoformat()
    }

@app.post("/api/v1/system/tasks/trigger-sync") 
def trigger_manual_sync():
    """Manually trigger finance sync"""
    
    if not redis_connected:
        raise HTTPException(status_code=503, detail="Redis not available")
    
    # Simulate queuing a sync task
    task_id = str(uuid.uuid4())
    
    try:
        # Add task to Redis queue (simulated)
        task_data = {
            "task_id": task_id,
            "task_type": "manual_sync",
            "queued_at": datetime.now().isoformat(),
            "status": "queued"
        }
        
        redis_client.lpush("finance_tasks", json.dumps(task_data))
        
        return {
            "status": "queued",
            "task_id": task_id,
            "message": "Manual sync triggered successfully",
            "estimated_completion": (datetime.now() + timedelta(minutes=5)).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue task: {str(e)}")

# =====================================
# MONITORING ENDPOINTS
# =====================================

@app.get("/api/v1/monitoring/system/health")
def system_health_check():
    """Comprehensive system health check"""
    
    # Simulate system metrics
    cpu_usage = random.uniform(15, 45)
    memory_usage = random.uniform(35, 75) 
    disk_usage = random.uniform(25, 60)
    
    # Determine overall status
    overall_status = "healthy"
    alerts = []
    
    if cpu_usage > 80:
        alerts.append("High CPU usage detected")
    if memory_usage > 85:
        alerts.append("High memory usage detected")
    if not redis_connected:
        alerts.append("Redis connection unavailable")
        overall_status = "degraded"
    
    return {
        "overall_status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "components": {
            "database": {
                "status": "healthy",
                "response_time_ms": random.randint(10, 50)
            },
            "redis": {
                "status": "healthy" if redis_connected else "unhealthy",
                "connection": redis_connected
            },
            "background_tasks": {
                "status": "healthy",
                "workers": 2,
                "active_tasks": random.randint(0, 3)
            },
            "system": {
                "cpu_percent": round(cpu_usage, 1),
                "memory_percent": round(memory_usage, 1), 
                "disk_percent": round(disk_usage, 1),
                "status": "healthy"
            }
        },
        "metrics": {
            "uptime_hours": round(random.uniform(24, 720), 1),
            "requests_today": random.randint(1000, 5000),
            "avg_response_time_ms": random.randint(50, 200)
        },
        "alerts": alerts
    }

@app.get("/api/v1/monitoring/processing/stats")
def processing_statistics(hours: int = 24):
    """Get processing statistics"""
    
    total_files = random.randint(15, 45)
    successful = int(total_files * random.uniform(0.85, 0.95))
    failed = total_files - successful
    
    return {
        "time_period_hours": hours,
        "processing_by_status": {
            "completed": successful,
            "failed": failed,
            "processing": random.randint(0, 2)
        },
        "processing_by_file_type": {
            "cash_book": random.randint(8, 15),
            "party_due_bill": random.randint(3, 8),
            "expenditure_summary": random.randint(2, 5)
        },
        "average_processing_time_seconds": round(random.uniform(45, 120), 1),
        "success_rate_percent": round((successful / total_files) * 100, 1),
        "recent_errors": [
            {
                "file_name": "problematic_file.xlsx",
                "error": "Invalid date format in row 23",
                "timestamp": (datetime.now() - timedelta(hours=3)).isoformat()
            }
        ] if failed > 0 else []
    }

@app.get("/api/v1/monitoring/alerts")
def get_system_alerts():
    """Get current system alerts"""
    
    alerts = []
    
    # Simulate some alerts
    if random.random() < 0.3:  # 30% chance of alerts
        alerts.append({
            "level": "warning",
            "message": "High processing load detected",
            "timestamp": datetime.now().isoformat(),
            "component": "background_tasks"
        })
    
    if not redis_connected:
        alerts.append({
            "level": "critical", 
            "message": "Redis connection unavailable",
            "timestamp": datetime.now().isoformat(),
            "component": "redis"
        })
    
    return {
        "alerts": alerts,
        "alert_count": len(alerts),
        "last_check": datetime.now().isoformat(),
        "system_status": "degraded" if alerts else "healthy"
    }

# =====================================
# UTILITY ENDPOINTS
# =====================================

@app.get("/api/v1/finance/summary")
def get_finance_summary():
    """Get financial summary"""
    return {
        "daily_summary": {
            "cash_in": 125000.50,
            "cash_out": 87500.25,
            "net_flow": 37500.25
        },
        "monthly_summary": {
            "revenue": 2750000.75,
            "expenses": 1890000.50,
            "profit": 860000.25
        },
        "top_parties": [
            {"name": "Rojina Enterprise", "amount": 450000.00},
            {"name": "Dhaka Suppliers", "amount": 380000.00},
            {"name": "Local Vendor", "amount": 290000.00}
        ]
    }

if __name__ == "__main__":
    print("🚀 Starting Complete OpsVista Finance API Server")
    print("=" * 60)
    print(f"📊 Redis Connected: {redis_connected}")
    print("🔗 Available Endpoints:")
    print("   • Health: http://localhost:8000/health")
    print("   • Dashboard: http://localhost:8000/api/v1/finance/dashboard/metrics")
    print("   • API Docs: http://localhost:8000/docs")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
