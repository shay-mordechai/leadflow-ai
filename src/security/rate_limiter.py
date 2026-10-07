# src/security/rate_limiter.py
from slowapi import Limiter
from fastapi import Request
import ipaddress
from src.config import settings
import logging

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


# AGENT FIX: Using Redis storage for the Rate Limiter instead of In-Memory.
# This ensures that when running multiple Gunicorn workers, the limits are shared globally.
try:
    limiter = create_limiter(settings.REDIS_URL)
    logger.info("🛡️ Redis Rate Limiter initialized successfully.")
except Exception as e:
    logger.warning(f"⚠️ Could not connect Rate Limiter to Redis, falling back to memory. Error: {e}")
    limiter = Limiter(key_func=get_real_ip)