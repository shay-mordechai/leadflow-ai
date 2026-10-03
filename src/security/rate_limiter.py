# src/security/rate_limiter.py
from slowapi import Limiter
from slowapi.util import get_remote_address
from src.config import settings
import logging

logger = logging.getLogger("SecurityLimiter")

# AGENT FIX: Using Redis storage for the Rate Limiter instead of In-Memory.
# This ensures that when running multiple Gunicorn workers, the limits are shared globally.
try:
    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri=settings.REDIS_URL, # Connects SlowAPI directly to Redis
        storage_fallback="memory"       # Fallback gracefully if Redis is temporarily down
    )
    logger.info("🛡️ Redis Rate Limiter initialized successfully.")
except Exception as e:
    logger.warning(f"⚠️ Could not connect Rate Limiter to Redis, falling back to memory. Error: {e}")
    limiter = Limiter(key_func=get_remote_address)