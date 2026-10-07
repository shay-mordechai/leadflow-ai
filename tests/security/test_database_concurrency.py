"""Security regression tests for tenant isolation and database concurrency."""

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.database import session as database_session
from src.database.models import Lead, User
from src.routers.sessions import upload_audio
from src.services.communication import whatsapp_pipeline


async def _run_pipeline_with_transaction_probe(monkeypatch) -> tuple[str, list[bool]]:
    """Run a mocked Gemini request while tracking whether a DB transaction is active."""
    transaction_state = {"active": False}
    transaction_states_during_ai: list[bool] = []

    class TrackedTransaction:
        async def __aenter__(self):
            transaction_state["active"] = True

        async def __aexit__(self, *_: object):
            transaction_state["active"] = False

    database = MagicMock()
    database.begin.side_effect = TrackedTransaction
    monkeypatch.setattr(
        whatsapp_pipeline,
        "_prepare_message_context",
        AsyncMock(
            return_value=(
                "ready",
                {
                    "user_id": uuid4(),
                    "lead_turn_prompt": "safe prompt",
                    "system_instruction": "safe system instruction",
                },
            )
        ),
    )
    monkeypatch.setattr(
        whatsapp_pipeline,
        "_release_ai_message_credit",
        AsyncMock(return_value=True),
    )

    async def generate_content(**_: object):
        transaction_states_during_ai.append(transaction_state["active"])
        raise RuntimeError("simulated Gemini response")

    client = MagicMock()
    client.models.generate_content = AsyncMock(side_effect=generate_content)
    result = await whatsapp_pipeline._process_single_message(
        database,
        {},
        [],
        {"id": "transaction-probe"},
        client,
    )
    return result, transaction_states_during_ai


async def _run_concurrent_reservations(
    database_url: str,
    initial_count: int,
    max_count: int,
) -> tuple[list[int | None], int]:
    """Exercise simultaneous conditional usage reservations against a real database."""
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(User.__table__.create)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        user = User(
            name="Test tenant",
            email=f"{uuid4()}@example.test",
            hashed_password="not-a-real-password-hash",
            monthly_ai_messages=initial_count,
        )
        db.add(user)
        await db.flush()
        user_id = user.id
        await db.commit()

    async def reserve() -> int | None:
        async with session_factory() as db:
            async with db.begin():
                return await whatsapp_pipeline._reserve_ai_message_credit(
                    db,
                    user_id,
                    max_count,
                )

    reservation_results = await asyncio.gather(reserve(), reserve())
    async with session_factory() as db:
        persisted_count = await db.scalar(
            select(User.monthly_ai_messages).where(User.id == user_id)
        )
    await engine.dispose()
    return reservation_results, int(persisted_count or 0)


@pytest.mark.asyncio
async def test_tenant_cannot_open_another_tenants_lead_session():
    """Cross-Tenant Data Leakage (RLS): lead lookup must be tenant-scoped to prevent access to another business's data."""
    database = MagicMock()
    query = database.query.return_value
    query.filter.return_value.first.return_value = None
    tenant_id = uuid4()
    other_lead_id = uuid4()
    current_user = MagicMock(id=tenant_id)

    with pytest.raises(HTTPException) as error:
        await upload_audio(
            lead_id=str(other_lead_id),
            file=MagicMock(),
            db=database,
            current_user=current_user,
        )

    assert error.value.status_code == 404
    filters = query.filter.call_args.args
    assert len(filters) == 2
    assert filters[1].left.name == Lead.user_id.key
    assert filters[1].left.table.name == Lead.__tablename__


def test_database_dependency_closes_session_when_consumer_raises(monkeypatch):
    """Connection Pool Leaks: request-scoped sessions must close even when downstream code raises."""
    db = MagicMock()
    monkeypatch.setattr(database_session, "SessionLocal", lambda: db)
    dependency = database_session.get_db()

    assert next(dependency) is db
    with pytest.raises(RuntimeError, match="request failed"):
        dependency.throw(RuntimeError("request failed"))

    db.close.assert_called_once_with()


@pytest.mark.asyncio
async def test_db_connection_is_released_before_waiting_for_gemini(monkeypatch):
    """DB Connection Pool Exhaustion: a slow LLM request must not retain an open database transaction."""
    result, transaction_states = await _run_pipeline_with_transaction_probe(monkeypatch)

    assert result == "gemini_failed"
    assert transaction_states == [False]


@pytest.mark.asyncio
async def test_webhook_transaction_does_not_span_external_llm_io(monkeypatch):
    """Database Deadlocks: webhook transactions must be committed before awaiting external model inference."""
    result, transaction_states = await _run_pipeline_with_transaction_probe(monkeypatch)

    assert result == "gemini_failed"
    assert transaction_states == [False]


@pytest.mark.asyncio
async def test_background_whatsapp_worker_owns_its_database_session(monkeypatch):
    """Thread-Safety in Background Tasks: background processing must create its own session, never reuse request state."""

    class AsyncContext:
        def __init__(self):
            self.entered = False
            self.exited = False

        async def __aenter__(self):
            self.entered = True
            return self

        async def __aexit__(self, *_: object):
            self.exited = True

    client_context = AsyncContext()
    database_context = AsyncContext()
    client_holder = MagicMock(aio=client_context)
    session_factory = MagicMock(return_value=database_context)
    monkeypatch.setattr(
        whatsapp_pipeline,
        "_create_gemini_client",
        lambda: client_holder,
    )
    monkeypatch.setattr(whatsapp_pipeline, "AsyncSessionLocal", session_factory)

    await whatsapp_pipeline.process_whatsapp_message(
        {"object": "whatsapp_business_account", "entry": []}
    )

    session_factory.assert_called_once_with()
    assert client_context.entered and client_context.exited
    assert database_context.entered and database_context.exited


@pytest.mark.asyncio
async def test_atomic_usage_reservations_do_not_lose_concurrent_updates(tmp_path):
    """Lost Updates (Race Conditions): concurrent usage increments must be atomic instead of overwriting each other."""
    results, persisted_count = await _run_concurrent_reservations(
        f"sqlite+aiosqlite:///{tmp_path / 'lost-updates.db'}",
        initial_count=0,
        max_count=10,
    )

    assert sorted(results) == [1, 2]
    assert persisted_count == 2


@pytest.mark.asyncio
async def test_atomic_usage_reservations_enforce_limit_concurrently(tmp_path):
    """Token Double-Spending: concurrent requests must not reserve beyond the tenant's remaining AI message quota."""
    results, persisted_count = await _run_concurrent_reservations(
        f"sqlite+aiosqlite:///{tmp_path / 'double-spend.db'}",
        initial_count=9,
        max_count=10,
    )

    assert sorted(result for result in results if result is not None) == [10]
    assert results.count(None) == 1
    assert persisted_count == 10
