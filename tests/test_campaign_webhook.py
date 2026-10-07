import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from src.routers.webhooks import campaign


class InMemoryRedis:
    def __init__(self):
        self._keys: set[str] = set()
        self._lock = threading.Lock()

    async def set(self, key: str, value: str, *, ex: int, nx: bool):
        with self._lock:
            if nx and key in self._keys:
                return None
            self._keys.add(key)
            return "OK"


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(campaign.router)
    monkeypatch.setattr(campaign, "redis_client", InMemoryRedis())
    with TestClient(app) as test_client:
        yield test_client


def test_campaign_webhook_requires_configured_tenant_key(client, monkeypatch):
    monkeypatch.delenv("CAMPAIGN_WEBHOOK_SECRET", raising=False)

    response = client.post(
        "/webhooks/leads/inbound",
        headers={"X-Tenant-Key": "not-configured"},
        json={
            "lead_name": "Ada Lovelace",
            "phone_number": "+972501234567",
            "campaign_source": "landing-page",
        },
    )

    assert response.status_code == 401


def test_campaign_webhook_validates_and_deduplicates_leads(
    client, monkeypatch
):
    monkeypatch.setenv("CAMPAIGN_WEBHOOK_SECRET", "test-secret")
    processed_leads = []
    monkeypatch.setattr(
        campaign,
        "trigger_outbound_ai_agent",
        processed_leads.append,
    )
    payload = {
        "lead_name": "Ada Lovelace",
        "phone_number": "+972501234567",
        "campaign_source": "landing-page",
        "notes": "Requested a product demo.",
    }
    headers = {"X-Tenant-Key": "test-secret"}

    first_response = client.post(
        "/webhooks/leads/inbound",
        headers=headers,
        json=payload,
    )
    duplicate_response = client.post(
        "/webhooks/leads/inbound",
        headers=headers,
        json=payload,
    )

    assert first_response.status_code == 200
    assert first_response.json() == {"status": "accepted"}
    assert duplicate_response.status_code == 200
    assert duplicate_response.json() == {"status": "accepted"}
    assert len(processed_leads) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {
            "lead_name": "Ada Lovelace",
            "phone_number": "972501234567",
            "campaign_source": "landing-page",
        },
        {
            "lead_name": "Ada Lovelace",
            "phone_number": "+972501234567",
            "campaign_source": "landing-page",
            "notes": "x" * 251,
        },
    ],
)
def test_campaign_webhook_rejects_invalid_payload(client, monkeypatch, payload):
    monkeypatch.setenv("CAMPAIGN_WEBHOOK_SECRET", "test-secret")

    response = client.post(
        "/webhooks/leads/inbound",
        headers={"X-Tenant-Key": "test-secret"},
        json=payload,
    )

    assert response.status_code == 422


def test_campaign_webhook_fails_closed_when_redis_is_unavailable(
    client, monkeypatch
):
    """Campaign Webhook Race Conditions (TOCTOU): do not silently fall back to process-local deduplication when Redis fails."""

    class UnavailableRedis:
        async def set(self, *_args, **_kwargs):
            raise RedisConnectionError("Redis is unavailable")

    monkeypatch.setenv("CAMPAIGN_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setattr(campaign, "redis_client", UnavailableRedis())

    response = client.post(
        "/webhooks/leads/inbound",
        headers={"X-Tenant-Key": "test-secret"},
        json={
            "lead_name": "Ada Lovelace",
            "phone_number": "+972501234567",
            "campaign_source": "landing-page",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Webhook idempotency service unavailable"
