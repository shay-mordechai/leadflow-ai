# src/worker.py
import logging
from celery import Celery
from celery.schedules import crontab
from src.config import settings

# Initialize Celery Application
celery_app = Celery(
    "leadflow_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["src.tasks.audio_tasks", "src.tasks.retention_tasks"],
)

# Configure Celery serialization to standard JSON
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # This prevents Celery from consuming too much memory
    worker_max_tasks_per_child=50,
    beat_schedule={
        "purge-expired-tenant-data": {
            "task": "purge_expired_tenant_data",
            "schedule": crontab(minute=0),  # hourly; records expire at TTL, not on a daily dump
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
