"""Security regression and unit tests for payment webhook signature validation and grace period DLP tagging."""

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from starlette.requests import Request

import pytest

from src.database.models import SubscriptionStatus, User
from src.routers import leads
from src.routers.webhooks import meshulam


def test_meshulam_signature_verification_valid():
    api_key = "test-meshulam-secret"
    data = {"transactionId": "12345", "sum": "100", "status": "1"}
    data_str = "123451001"
    sig = hmac.new(api_key.encode(), data_str.encode(), hashlib.sha256).hexdigest()
    data["signature"] = sig

    assert meshulam.verify_meshulam_signature(data, api_key) is True


def test_meshulam_signature_verification_invalid():
    api_key = "test-meshulam-secret"
    data = {"transactionId": "12345", "sum": "100", "status": "1", "signature": "invalid-sig"}
    assert meshulam.verify_meshulam_signature(data, api_key) is False


def test_meshulam_signature_verification_missing():
    api_key = "test-meshulam-secret"
    data = {"transactionId": "12345", "sum": "100", "status": "1"}
    assert meshulam.verify_meshulam_signature(data, api_key) is False


@pytest.mark.asyncio
async def test_get_my_leads_grace_period_active(monkeypatch):
    """Test grace period active header assignment when now < grace_period_ends_at."""
    now = datetime.now(UTC)
    future_time = now + timedelta(hours=12)

    user = User(
        id="uuid-1",
        email="test@example.com",
        subscription_status=SubscriptionStatus.PAST_DUE,
        grace_period_ends_at=future_time,
    )

    response = MagicMock()
    response.headers = {}

    db_session = MagicMock()
    db_session.query.return_value.filter.return_value.options.return_value.options.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/leads/my",
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    request = Request(scope)
    await leads.get_my_leads(
        request=request, response=response, limit=50, offset=0, db=db_session, current_user=user
    )

    assert response.headers.get("X-Subscription-Alert") == "grace_period_active"
    assert "X-Grace-Period-Remaining" in response.headers
    assert "X-Data-TTL" not in response.headers


@pytest.mark.asyncio
async def test_get_my_leads_grace_period_expired(monkeypatch):
    """Test X-Data-TTL: 1 header assignment when grace period has expired (now >= grace_period_ends_at)."""
    now = datetime.now(UTC)
    past_time = now - timedelta(hours=1)

    user = User(
        id="uuid-1",
        email="test@example.com",
        subscription_status=SubscriptionStatus.PAST_DUE,
        grace_period_ends_at=past_time,
    )

    response = MagicMock()
    response.headers = {}

    db_session = MagicMock()
    db_session.query.return_value.filter.return_value.options.return_value.options.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/leads/my",
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    request = Request(scope)
    await leads.get_my_leads(
        request=request, response=response, limit=50, offset=0, db=db_session, current_user=user
    )

    assert response.headers.get("X-Data-TTL") == "1"
    assert "X-Subscription-Alert" not in response.headers
