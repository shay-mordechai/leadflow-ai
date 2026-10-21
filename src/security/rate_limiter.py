# src/security/rate_limiter.py
import ipaddress
import logging
import os

from fastapi import Request
from slowapi import Limiter

from src.config import settings

logger = logging.getLogger("SecurityLimiter")


def get_real_ip(request: Request) -> str:
    """Trust Cloudflare client addresses only when the socket peer is configured as a proxy."""
    peer = request.client.host if request.client else ""
    try:
        peer_ip = ipaddress.ip_address(peer)
    except ValueError:
        return peer or "unknown"

    for trusted_range in settings.TRUSTED_PROXY_IPS:
        try:
            if peer_ip in ipaddress.ip_network(trusted_range, strict=False):
                forwarded_ip = ipaddress.ip_address(
                    request.headers.get("CF-Connecting-IP", "")
                )
                return str(forwarded_ip)
        except ValueError:
            continue
    return str(peer_ip)


def create_limiter(redis_url: str) -> Limiter:
    """Construct SlowAPI with Redis storage and its supported memory fallback."""
    return Limiter(
        key_func=get_real_ip,
        storage_uri=redis_url,
        in_memory_fallback_enabled=True,
    )


def init_limiter() -> Limiter:
    """Initialize rate limiter with production fail-fast check and fallback support."""
    try:
        limiter_instance = create_limiter(settings.REDIS_URL)
        logger.info("🛡️ Redis Rate Limiter initialized successfully.")
        return limiter_instance
    except Exception as e:  # noqa: BLE001
        env = (
            os.getenv("APP_ENV")
            or getattr(settings, "APP_ENV", "development")
        ).lower()
        if env == "production":
            logger.critical(
                f"CRITICAL: Redis is required for distributed rate limiting in production (PID {os.getpid()}). Error: {e}"
            )
            raise RuntimeError(
                "CRITICAL: Redis is required for distributed rate limiting in production."
            )
        else:
            logger.warning(
                f"EVENT: RATE_LIMITER_REDIS_FALLBACK | Could not connect Rate Limiter to Redis, falling back to in-memory (PID {os.getpid()}). Error: {e}"
            )
            return Limiter(key_func=get_real_ip)


limiter = init_limiter()

