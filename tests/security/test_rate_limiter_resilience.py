# tests/security/test_rate_limiter_resilience.py
import os
from unittest.mock import patch

import pytest
from slowapi import Limiter

import src.security.rate_limiter


def test_rate_limiter_production_failure() -> None:
    """SEC-02: In production environment, rate limiter initialization failure on Redis must raise RuntimeError."""
    with (
        patch(
            "src.security.rate_limiter.create_limiter",
            side_effect=Exception("Redis connection error"),
        ),
        patch.dict(os.environ, {"APP_ENV": "production"}),
        pytest.raises(RuntimeError, match="CRITICAL: Redis is required"),
    ):
        src.security.rate_limiter.init_limiter()


def test_rate_limiter_test_env_fallback() -> None:
    """SEC-02: In test environment, rate limiter initialization failure on Redis falls back to in-memory Limiter."""
    with (
        patch(
            "src.security.rate_limiter.create_limiter",
            side_effect=Exception("Redis connection error"),
        ),
        patch.dict(os.environ, {"APP_ENV": "test"}),
    ):
        lim = src.security.rate_limiter.init_limiter()
        assert isinstance(lim, Limiter)
