# src/tasks/watchdog_tasks.py
import asyncio
import logging

import redis.asyncio as aioredis

from src.config import settings
from src.services.monitoring.watchdog import ProductionWatchdog
from src.worker import celery_app

logger = logging.getLogger("WatchdogTask")


@celery_app.task(name="run_production_watchdog", bind=True, max_retries=1)
def run_production_watchdog(self):
    """Celery periodic task executing production monitoring checks and anomaly alerts."""
    logger.info("Running production monitoring watchdog checks...")
    try:

        async def _run():
            redis_client = None
            try:
                redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
                results = await ProductionWatchdog.run_checks(redis_client)
                return results
            finally:
                if redis_client:
                    await redis_client.close()

        results = asyncio.run(_run())
        logger.info(f"Watchdog completed successfully: {results}")
        return results
    except Exception as exc:
        logger.error(f"Watchdog execution failed: {exc}")
        raise exc
