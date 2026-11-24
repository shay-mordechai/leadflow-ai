# src/security/idempotency.py
import logging

from src.config import settings

logger = logging.getLogger("WebhookIdempotency")

_MEMORY_IDEMPOTENCY_STORE: set[str] = set()


def check_and_claim_idempotency(provider: str, message_id: str, ttl_seconds: int = 86400) -> bool:
    """
    Checks if a webhook message ID has already been processed.
    Atomically claims it in Redis using SET NX with TTL.
    Falls back to in-memory set for local/test environments if Redis is unavailable.
    Returns True if successfully claimed (first time), or False if duplicate.
    """
    if not message_id:
        return True

    key = f"webhook:idempotency:{provider.lower()}:{message_id}"

    try:
        import redis

        r = redis.from_url(settings.REDIS_URL, decode_responses=True)
        acquired = r.set(key, "1", ex=ttl_seconds, nx=True)
        r.close()
        if acquired:
            return True
        logger.info(f"Duplicate webhook detected for {provider} message ID: {message_id}")
        return False
    except Exception as exc:
        logger.warning(f"Redis idempotency fallback to memory store: {exc}")
        if key in _MEMORY_IDEMPOTENCY_STORE:
            logger.info(
                f"Duplicate webhook detected in memory store for {provider} message ID: {message_id}"
            )
            return False
        _MEMORY_IDEMPOTENCY_STORE.add(key)
        return True
