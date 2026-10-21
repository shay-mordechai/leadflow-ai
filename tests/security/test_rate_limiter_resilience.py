# tests/security/test_rate_limiter_resilience.py
from unittest.mock import patch
import pytest
from slowapi import Limiter
from src.config import settings


def test_rate_limiter_production_failure() -> None:
    """SEC-02: In production environment, rate limiter initialization failure on Redis must raise RuntimeError."""
    with patch("src.security.rate_limiter.create_limiter", side_effect=Exception("Redis down")), \
         patch.object(settings, "ENVIRONMENT", "production"):
        # Re-importing or reloading rate_limiter module behavior under production failure
        import importlib
        import src.security.rate_limiter
        with pytest.raises(RuntimeError, match="CRITICAL: Redis is required"):
            importlib.reload(src.security.rate_limiter)


def test_rate_limiter_test_env_fallback() -> None:
    """SEC-02: In test environment, rate limiter initialization failure on Redis falls back to in-memory Limiter."""
    with patch("src.security.rate_limiter.create_limiter", side_effect=Exception("Redis down")), \
         patch.object(settings, "ENVIRONMENT", "test"):
        import importlib
        import src.security.rate_limiter
        importlib.reload(src.security.rate_limiter)
        assert isinstance(src.security.rate_limiter.limiter, Limiter)
