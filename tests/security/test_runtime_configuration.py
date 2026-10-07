"""Regression tests for external service initialization configuration."""

from src.security import rate_limiter


def test_slowapi_limiter_accepts_redis_uri_and_supported_fallback() -> None:
    """Redis rate limiting: supported SlowAPI options must initialize the shared Redis backend."""
    limiter = rate_limiter.create_limiter("redis://localhost:6379/0")

    assert limiter._storage_uri == "redis://localhost:6379/0"
    assert limiter._in_memory_fallback_enabled is True
