# src/worker.py
import logging
from celery import Celery
from src.config import settings

# Initialize Celery Application
celery_app = Celery(
    "leadflow_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

# Configure Celery serialization to standard JSON
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    # This prevents Celery from consuming too much memory
    worker_max_tasks_per_child=50,
)

logger = logging.getLogger("CeleryWorker")

@celery_app.task(name="ping_test")
def ping_test(message: str):
    """
    A simple test task to verify the worker is listening.
    """
    logger.info(f"🏓 PONG! Received message: {message}")
    return f"Processed: {message}"

# Note: In the next step, we will import audio_tasks.py here!