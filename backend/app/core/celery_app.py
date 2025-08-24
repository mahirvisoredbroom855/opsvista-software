# Celery Configuration for Background Tasks
from celery import Celery
from celery.schedules import crontab
import os
from dotenv import load_dotenv

load_dotenv()

# Create Celery app
celery_app = Celery(
    "opsvista_finance",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    include=[
        'app.features.finance.tasks'  # Import our finance tasks
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Dhaka',
    enable_utc=True,
    
    # Task routing
    task_routes={
        'app.features.finance.tasks.*': {'queue': 'finance'},
    },
    
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    
    # Result backend settings
    result_expires=3600,  # 1 hour
    
    # Beat schedule (periodic tasks)
    beat_schedule={
        'sync-finance-files': {
            'task': 'app.features.finance.tasks.scheduled_finance_sync',
            'schedule': 180.0,  # Every 3 minutes
            'options': {'queue': 'finance'}
        },
        'cleanup-old-processing-records': {
            'task': 'app.features.finance.tasks.cleanup_old_records',
            'schedule': crontab(hour=2, minute=0),  # Every day at 2 AM
            'options': {'queue': 'finance'}
        },
    },
)

# Task autodiscovery
celery_app.autodiscover_tasks()

if __name__ == '__main__':
    celery_app.start()
