"""
Celery Application Configuration
"""
import os
from celery import Celery
from celery.schedules import crontab

from app.config import settings


# Create Celery app
celery_app = Celery(
    "obie",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.ingestion_tasks", "app.tasks.enrichment_tasks"],
)

# Configure Celery
celery_app.conf.update(
    task_serializer=settings.celery_task_serializer,
    accept_content=settings.celery_accept_content,
    result_serializer=settings.celery_result_serializer,
    timezone=settings.celery_timezone,
    enable_utc=True,
    
    # Task settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    
    # Rate limiting
    worker_prefetch_multiplier=1,
    
    # Scheduled tasks
    beat_schedule={
        # Run ingestion every hour
        "hourly-ingestion": {
            "task": "app.tasks.ingestion_tasks.run_scheduled_ingestion",
            "schedule": crontab(minute=0),  # Every hour
        },
        # Daily summary report
        "daily-summary": {
            "task": "app.tasks.ingestion_tasks.generate_daily_summary",
            "schedule": crontab(hour=8, minute=0),  # 8 AM daily
        },
    },
)


# Auto-discover tasks
celery_app.autodiscover_tasks()


@celery_app.task(bind=True)
def debug_task(self):
    """Debug task to verify Celery is working."""
    print(f"Request: {self.request!r}")
    return "OK"
