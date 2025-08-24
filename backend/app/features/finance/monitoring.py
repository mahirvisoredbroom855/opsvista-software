# System Monitoring and Health Checks
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import Dict, Any, List
import psutil
import os

from .models import FinanceFileProcessing, FactFinance
from app.core.supabase_client import get_db

monitoring_router = APIRouter(prefix="/api/v1/monitoring", tags=["Monitoring"])

@monitoring_router.get("/system/health")
async def system_health_check(db: Session = Depends(get_db)):
    """Comprehensive system health check"""
    
    health_status = {
        "overall_status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {},
        "metrics": {},
        "alerts": []
    }
    
    try:
        # Database health
        db.execute("SELECT 1")
        health_status["components"]["database"] = {
            "status": "healthy",
            "response_time_ms": 0  # TODO: Measure actual response time
        }
    except Exception as e:
        health_status["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["overall_status"] = "degraded"
    
    # System resources
    try:
        health_status["components"]["system"] = {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
            "status": "healthy"
        }
        
        # Add alerts for high resource usage
        if psutil.cpu_percent() > 80:
            health_status["alerts"].append("High CPU usage detected")
        if psutil.virtual_memory().percent > 85:
            health_status["alerts"].append("High memory usage detected")
            
    except Exception as e:
        health_status["components"]["system"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Background task health
    try:
        from app.core.celery_app import celery_app
        inspect = celery_app.control.inspect()
        
        stats = inspect.stats()
        active_tasks = inspect.active()
        
        if stats:
            health_status["components"]["background_tasks"] = {
                "status": "healthy",
                "workers": len(stats),
                "active_tasks": sum(len(tasks) for tasks in active_tasks.values()) if active_tasks else 0
            }
        else:
            health_status["components"]["background_tasks"] = {
                "status": "unhealthy",
                "error": "No workers available"
            }
            health_status["overall_status"] = "degraded"
            
    except Exception as e:
        health_status["components"]["background_tasks"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Processing metrics
    try:
        # Recent processing activity (last 24 hours)
        since_time = datetime.now() - timedelta(hours=24)
        
        recent_processing = db.query(func.count(FinanceFileProcessing.id)).filter(
            FinanceFileProcessing.created_at >= since_time
        ).scalar()
        
        successful_processing = db.query(func.count(FinanceFileProcessing.id)).filter(
            FinanceFileProcessing.created_at >= since_time,
            FinanceFileProcessing.status == 'completed'
        ).scalar()
        
        failed_processing = db.query(func.count(FinanceFileProcessing.id)).filter(
            FinanceFileProcessing.created_at >= since_time,
            FinanceFileProcessing.status == 'failed'
        ).scalar()
        
        health_status["metrics"]["processing_24h"] = {
            "total": recent_processing,
            "successful": successful_processing,
            "failed": failed_processing,
            "success_rate": (successful_processing / recent_processing * 100) if recent_processing > 0 else 0
        }
        
        # Add alert for high failure rate
        if recent_processing > 0 and (failed_processing / recent_processing) > 0.2:
            health_status["alerts"].append("High processing failure rate detected")
            
    except Exception as e:
        health_status["metrics"]["processing_24h"] = {"error": str(e)}
    
    # Set overall status based on components
    if health_status["alerts"]:
        health_status["overall_status"] = "degraded"
    
    unhealthy_components = [
        comp for comp in health_status["components"].values() 
        if comp.get("status") == "unhealthy"
    ]
    
    if unhealthy_components:
        health_status["overall_status"] = "unhealthy"
    
    return health_status

@monitoring_router.get("/processing/stats")
async def processing_statistics(
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """Get processing statistics for specified time period"""
    
    since_time = datetime.now() - timedelta(hours=hours)
    
    # Processing counts by status
    processing_stats = db.query(
        FinanceFileProcessing.status,
        func.count(FinanceFileProcessing.id).label('count')
    ).filter(
        FinanceFileProcessing.created_at >= since_time
    ).group_by(FinanceFileProcessing.status).all()
    
    # Processing counts by file type
    file_type_stats = db.query(
        FinanceFileProcessing.file_type,
        func.count(FinanceFileProcessing.id).label('count')
    ).filter(
        FinanceFileProcessing.created_at >= since_time
    ).group_by(FinanceFileProcessing.file_type).all()
    
    # Processing time averages
    avg_processing_time = db.query(
        func.avg(
            func.extract('epoch', FinanceFileProcessing.processing_completed - FinanceFileProcessing.processing_started)
        ).label('avg_seconds')
    ).filter(
        FinanceFileProcessing.created_at >= since_time,
        FinanceFileProcessing.status == 'completed'
    ).scalar()
    
    # Recent errors
    recent_errors = db.query(FinanceFileProcessing).filter(
        FinanceFileProcessing.created_at >= since_time,
        FinanceFileProcessing.status == 'failed'
    ).order_by(FinanceFileProcessing.created_at.desc()).limit(10).all()
    
    return {
        "time_period_hours": hours,
        "processing_by_status": {stat.status: stat.count for stat in processing_stats},
        "processing_by_file_type": {stat.file_type: stat.count for stat in file_type_stats},
        "average_processing_time_seconds": float(avg_processing_time) if avg_processing_time else 0,
        "recent_errors": [
            {
                "file_name": error.source_file,
                "error": error.error_details,
                "timestamp": error.created_at.isoformat()
            }
            for error in recent_errors
        ]
    }

@monitoring_router.get("/data/quality")
async def data_quality_metrics(db: Session = Depends(get_db)):
    """Get data quality metrics"""
    
    # Average data quality scores
    avg_quality_score = db.query(
        func.avg(FactFinance.data_quality_score)
    ).scalar()
    
    # Quality score distribution
    quality_distribution = db.query(
        func.case(
            (FactFinance.data_quality_score >= 0.9, 'excellent'),
            (FactFinance.data_quality_score >= 0.7, 'good'),
            (FactFinance.data_quality_score >= 0.5, 'fair'),
            else_='poor'
        ).label('quality_category'),
        func.count(FactFinance.finance_id).label('count')
    ).group_by('quality_category').all()
    
    # Recent transactions with low quality scores
    low_quality_transactions = db.query(FactFinance).filter(
        FactFinance.data_quality_score < 0.5
    ).order_by(FactFinance.loaded_at.desc()).limit(10).all()
    
    return {
        "average_quality_score": float(avg_quality_score) if avg_quality_score else 0,
        "quality_distribution": {dist.quality_category: dist.count for dist in quality_distribution},
        "low_quality_transactions": [
            {
                "transaction_id": str(trans.finance_id),
                "quality_score": trans.data_quality_score,
                "source": trans.source_reference,
                "date": trans.transaction_date.isoformat() if trans.transaction_date else None
            }
            for trans in low_quality_transactions
        ]
    }

@monitoring_router.get("/alerts")
async def get_system_alerts(db: Session = Depends(get_db)):
    """Get current system alerts"""
    
    alerts = []
    
    # Check for failed processing in last hour
    recent_failures = db.query(func.count(FinanceFileProcessing.id)).filter(
        FinanceFileProcessing.created_at >= datetime.now() - timedelta(hours=1),
        FinanceFileProcessing.status == 'failed'
    ).scalar()
    
    if recent_failures > 0:
        alerts.append({
            "level": "warning",
            "message": f"{recent_failures} file processing failures in the last hour",
            "timestamp": datetime.now().isoformat()
        })
    
    # Check for stale data
    latest_transaction = db.query(func.max(FactFinance.loaded_at)).scalar()
    if latest_transaction and (datetime.now() - latest_transaction) > timedelta(hours=6):
        alerts.append({
            "level": "warning", 
            "message": "No new transaction data in the last 6 hours",
            "timestamp": datetime.now().isoformat()
        })
    
    # Check system resources
    try:
        if psutil.cpu_percent() > 80:
            alerts.append({
                "level": "critical",
                "message": f"High CPU usage: {psutil.cpu_percent():.1f}%",
                "timestamp": datetime.now().isoformat()
            })
        
        if psutil.virtual_memory().percent > 85:
            alerts.append({
                "level": "critical",
                "message": f"High memory usage: {psutil.virtual_memory().percent:.1f}%",
                "timestamp": datetime.now().isoformat()
            })
    except:
        pass
    
    return {
        "alerts": alerts,
        "alert_count": len(alerts),
        "last_check": datetime.now().isoformat()
    }
