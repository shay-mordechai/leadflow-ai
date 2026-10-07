"""Security regression tests for inbound and outbound webhook behavior."""

import json
import asyncio
import hashlib
import hmac
import threading
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import BackgroundTasks, HTTPException
from starlette.requests import Request

from src.schemas.ai_response import WhatsAppAgentResponse
from src.routers.webhooks import campaign, whatsapp
from src.services.communication import whatsapp_pipeline


def test_meta_webhook_timestamp_must_be_within_five_minutes():
    """Webhook Replay Attacks: signed Meta events older than five minutes must be rejected."""
    current_time = 2_000_000_000
    stale_payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {"timestamp": str(current_time - 301)}
                            ]
                        }
                    }
                ]
            }
        ]
    }

    assert not whatsapp._has_fresh_meta_timestamps(
        stale_payload,
        now=current_time,
    )


def test_meta_webhook_accepts_current_timestamp():
    """Webhook Replay Attacks: valid current Meta event timestamps must continue to be accepted."""
    current_time = 2_000_000_000
    fresh_payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {"timestamp": str(current_time - 300)}
                            ]
                        }
                    }
                ]
            }
        ]
    }

    assert whatsapp._has_fresh_meta_timestamps(
        fresh_payload,
        now=current_time,
    )


@pytest.mark.asyncio
async def test_whatsapp_route_rejects_stale_signed_event(monkeypatch):
    """Webhook Replay Attacks: a valid signature must not make a stale event eligible for background processing."""
    current_time = 2_000_000_000
    body = json.dumps(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {"timestamp": str(current_time - 301)}
                                ]
                            }
                        }
                    ]
                }
            ],
        }
    ).encode()
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 12345),
            "scheme": "http",
        },
        receive=AsyncMock(return_value={"type": "http.request", "body": body}),
    )
    monkeypatch.setattr(whatsapp, "verify_whatsapp_signature", AsyncMock())
    monkeypatch.setattr(whatsapp.time, "time", lambda: current_time)
    background_tasks = BackgroundTasks()

    with pytest.raises(HTTPException) as error:
        await whatsapp.handle_whatsapp_webhook(background_tasks, request)

    assert error.value.status_code == 401
    assert not background_tasks.tasks


@pytest.mark.asyncio
async def test_whatsapp_signature_validation_uses_constant_time_comparison(monkeypatch):
    """Timing Attacks on Signatures: valid webhook signatures must be checked with constant-time comparison."""
    secret = "test-app-secret"
    body = b'{"object":"whatsapp_business_account"}'
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"x-hub-signature-256", f"sha256={signature}".encode())],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 12345),
            "scheme": "http",
        },
        receive=AsyncMock(return_value={"type": "http.request", "body": body}),
    )
    monkeypatch.setattr(whatsapp.settings, "WHATSAPP_APP_SECRET", secret)
    compare_digest = MagicMock(wraps=hmac.compare_digest)
    monkeypatch.setattr(whatsapp.hmac, "compare_digest", compare_digest)

    await whatsapp.verify_whatsapp_signature(request)

    compare_digest.assert_called_once()


@pytest.mark.asyncio
async def test_campaign_idempotency_uses_atomic_redis_claim(monkeypatch):
    """Campaign Webhook Race Conditions (TOCTOU): use Redis SET NX with a 24-hour TTL to prevent cross-worker duplicates."""
    redis_client = AsyncMock()
    redis_client.set.return_value = "OK"
    monkeypatch.setattr(campaign, "redis_client", redis_client)

    claimed = await campaign._reserve_lead_idempotency_key("+972501234567")

    assert claimed
    key, value = redis_client.set.await_args.args
    assert key.startswith("campaign:webhook:lead:")
    assert value == "1"
    assert redis_client.set.await_args.kwargs == {"ex": 24 * 60 * 60, "nx": True}


@pytest.mark.asyncio
async def test_campaign_redis_claim_is_shared_across_concurrent_callers(monkeypatch):
    """Campaign Webhook Race Conditions (TOCTOU): concurrent workers must observe one shared atomic reservation."""

    class SharedRedis:
        def __init__(self):
            self._keys: set[str] = set()
            self._lock = threading.Lock()

        async def set(self, key: str, value: str, *, ex: int, nx: bool):
            with self._lock:
                if nx and key in self._keys:
                    return None
                self._keys.add(key)
                return "OK"

    monkeypatch.setattr(campaign, "redis_client", SharedRedis())

    results = await asyncio.gather(
        campaign._reserve_lead_idempotency_key("+972501234567"),
        campaign._reserve_lead_idempotency_key("+972501234567"),
    )

    assert sorted(results) == [False, True]


async def _run_whatsapp_pipeline_with_send_result(monkeypatch, send_result):
    """Exercise outbound persistence with a controlled provider response."""

    class Transaction:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_: object):
            return False

    database = MagicMock()
    database.begin.side_effect = Transaction
    database.get = AsyncMock(return_value=MagicMock(bot_active=True))
    monkeypatch.setattr(
        whatsapp_pipeline,
        "_prepare_message_context",
        AsyncMock(
            return_value=(
                "ready",
                {
                    "user_id": "tenant-id",
                    "lead_id": "lead-id",
                    "sender_id": "972501234567",
                    "phone_number_id": "business-number",
                    "lead_turn_prompt": "safe prompt",
                    "system_instruction": "safe system",
                },
            )
        ),
    )
    monkeypatch.setattr(
        whatsapp_pipeline,
        "_release_ai_message_credit",
        AsyncMock(return_value=True),
    )
    model_client = MagicMock()
    model_client.models.generate_content = AsyncMock(
        return_value=MagicMock(
            parsed=WhatsAppAgentResponse(
                reply_text="Thanks for contacting us.",
                lead_intent="INQUIRY",
                lead_qualification_score=20,
                needs_human_escalation=False,
            )
        )
    )
    if isinstance(send_result, Exception):
        send_message = AsyncMock(side_effect=send_result)
    else:
        send_message = AsyncMock(return_value=send_result)
    monkeypatch.setattr(whatsapp_pipeline, "send_whatsapp_message", send_message)

    result = await whatsapp_pipeline._process_single_message(
        database,
        {},
        [],
        {"id": "inbound-message"},
        model_client,
    )
    return result, database.add, send_message


@pytest.mark.asyncio
async def test_outbound_message_is_not_persisted_when_meta_rejects_send(monkeypatch):
    """State Machine Desync: rejected Meta sends must not be recorded as successful outbound messages."""
    result, add_message, send_message = await _run_whatsapp_pipeline_with_send_result(
        monkeypatch,
        RuntimeError("Meta rejected message"),
    )

    assert result == "meta_send_failed"
    send_message.assert_awaited_once()
    add_message.assert_not_called()


@pytest.mark.asyncio
async def test_outbound_message_is_persisted_only_after_meta_accepts_send(monkeypatch):
    """State Machine Desync: outbound delivery records must only be created after Meta returns success."""
    result, add_message, send_message = await _run_whatsapp_pipeline_with_send_result(
        monkeypatch,
        "wamid.accepted",
    )

    assert result == "ai_replied"
    send_message.assert_awaited_once()
    persisted_message = add_message.call_args.args[0]
    assert persisted_message.sender_type == "bot"
    assert persisted_message.external_id == "wamid.accepted"
