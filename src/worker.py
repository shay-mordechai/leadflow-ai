# src/worker.py
import logging

from celery import Celery
from celery.schedules import crontab

from src.config import settings

# Initialize Celery Application and include all task modules
celery_app = Celery(
    "leadflow_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "src.tasks.audio_tasks",
        "src.tasks.backup_tasks",
        "src.tasks.billing_tasks",
        "src.tasks.followup_tasks",
        "src.tasks.marketing_advisor",
        "src.tasks.retention_tasks",
        "src.tasks.watchdog_tasks",
    ],
)

# Configure Celery serialization, reliability guarantees, and periodic schedules (Beat)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # Prevent memory leaks (memory optimization per child process)
    worker_max_tasks_per_child=50,
    task_routes={
        "src.tasks.marketing_advisor.dispatch_weekly_marketing_digests": {"queue": "rag_read"},
        "src.tasks.marketing_advisor.analyze_tenant_marketing": {"queue": "rag_read"},
        "src.tasks.marketing_advisor.deliver_marketing_digest": {"queue": "mutations"},
        "src.tasks.marketing_advisor.dispatch_weekly_content_discovery": {"queue": "rag_read"},
        "src.tasks.marketing_advisor.discover_tenant_content": {"queue": "rag_read"},
        "src.tasks.marketing_advisor.persist_content_suggestions": {"queue": "mutations"},
        "src.tasks.rag_*": {"queue": "rag_read"},
        "rag_*": {"queue": "rag_read"},
        "*.rag_*": {"queue": "rag_read"},
        "*": {"queue": "default"},
    },
    beat_schedule={
        "run-production-watchdog": {
            "task": "run_production_watchdog",
            "schedule": crontab(minute="*/5"),  # Every 5 minutes
        },
        "purge-expired-tenant-data": {
            "task": "purge_expired_tenant_data",
            "schedule": crontab(minute=0),  # Hourly cleanup
        },
        "run-smart-followups": {
            "task": "src.tasks.followup_tasks.process_smart_followups",
            "schedule": crontab(minute=0),  # Hourly check for stale leads
        },
        "run-daily-backup": {
            "task": "src.tasks.backup_tasks.run_backup",
            "schedule": crontab(hour=2, minute=0),  # Daily at 02:00 AM
        },
        "weekly-marketing-advisor-digest": {
            "task": "src.tasks.marketing_advisor.dispatch_weekly_marketing_digests",
            "schedule": crontab(minute=0, hour=8, day_of_week=1),  # Mondays at 08:00 AM UTC
        },
        "weekly-content-discovery": {
            "task": "src.tasks.marketing_advisor.dispatch_weekly_content_discovery",
            "schedule": crontab(
                minute=0, hour=7, day_of_week=0
            ),  # Sundays at 07:00 AM UTC (09:00 IST)
        },
    },
)

logger = logging.getLogger("CeleryWorker")


@celery_app.task(name="ping_test")
def ping_test(message: str):
    """
    A simple test task to verify the worker is listening.
    """
    logger.info(f"🏓 PONG! Received message: {message}")
    return f"Processed: {message}"
