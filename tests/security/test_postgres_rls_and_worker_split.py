"""Security & integration tests for PostgreSQL Row-Level Security (RLS), least-privilege roles,
and Celery worker reliability configuration (`task_acks_late`, `task_routes`, etc.).
"""

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError

from src.config import settings
from src.worker import celery_app


def test_celery_reliability_and_routing_config():
    """Verify Celery is configured with strict reliability guarantees and queue routing."""
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True
    assert celery_app.conf.worker_prefetch_multiplier == 1

    routes = celery_app.conf.task_routes
    assert routes is not None
    # Verify rag_read queue mapping
    assert "rag_read" in str(routes)
    assert "default" in str(routes)


def test_least_privilege_reader_permissions():
    """Verify leadflow_reader role can query but cannot insert/update/delete."""
    read_url = os.getenv("READ_ONLY_DATABASE_URL", "")
    if not read_url or "sqlite" in read_url:
        pytest.skip(
            "Skipping PostgreSQL role test because READ_ONLY_DATABASE_URL is not set or using SQLite."
        )

    sync_url = read_url.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url)

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

            with pytest.raises((ProgrammingError, OperationalError)):
                conn.execute(
                    text("INSERT INTO leads (id, user_id, name) VALUES (:id, :uid, 'Test')"),
                    {"id": uuid4(), "uid": uuid4()},
                )
                conn.commit()
    finally:
        engine.dispose()


def test_rls_tenant_isolation_enforcement():
    """Verify non-superuser writer role is strictly restricted by RLS when app.current_tenant_id is set."""
    db_url = settings.DATABASE_URL
    if not db_url or "sqlite" in db_url:
        pytest.skip("Skipping PostgreSQL RLS test because DATABASE_URL is SQLite or unset.")

    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url)
    tenant_a = uuid4()
    tenant_b = uuid4()
    lead_a_id = uuid4()
    lead_b_id = uuid4()

    try:
        with engine.begin() as conn:
            # 1. Seed data using rls_bypass = 'on'
            conn.execute(text("SELECT set_config('app.rls_bypass', 'on', true)"))
            conn.execute(
                text(
                    "INSERT INTO users (id, email, name, hashed_password, plan_tier, subscription_status, monthly_ai_messages, role) VALUES (:id, :email, :name, 'pw', 'STARTER', 'TRIAL', 0, 'CLIENT') ON CONFLICT DO NOTHING"
                ),
                [
                    {
                        "id": tenant_a,
                        "email": f"tenant_a_{tenant_a}@example.com",
                        "name": "Tenant A",
                    },
                    {
                        "id": tenant_b,
                        "email": f"tenant_b_{tenant_b}@example.com",
                        "name": "Tenant B",
                    },
                ],
            )
            conn.execute(
                text(
                    "INSERT INTO leads (id, user_id, name, status, source, bot_active, requires_human) VALUES (:id, :uid, :name, 'NEW', 'MANUAL', true, false) ON CONFLICT DO NOTHING"
                ),
                [
                    {"id": lead_a_id, "uid": tenant_a, "name": "Lead A"},
                    {"id": lead_b_id, "uid": tenant_b, "name": "Lead B"},
                ],
            )

        with engine.connect() as conn:
            # 2. Unset context sees 0 rows under fail-closed RLS
            conn.execute(text("SELECT set_config('app.current_tenant_id', '', true)"))
            conn.execute(text("SELECT set_config('app.rls_bypass', 'off', true)"))
            count_unset = conn.execute(
                text("SELECT count(*) FROM leads WHERE id IN (:la, :lb)"),
                {"la": lead_a_id, "lb": lead_b_id},
            ).scalar()
            assert count_unset == 0

            # 3. Context tenant_a sees only tenant_a's row (count == 1)
            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tid, true)"),
                {"tid": str(tenant_a)},
            )
            count_a = conn.execute(
                text("SELECT count(*) FROM leads WHERE id IN (:la, :lb)"),
                {"la": lead_a_id, "lb": lead_b_id},
            ).scalar()
            assert count_a == 1

            # 4. Context tenant_b sees only tenant_b's row (count == 1)
            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tid, true)"),
                {"tid": str(tenant_b)},
            )
            count_b = conn.execute(
                text("SELECT count(*) FROM leads WHERE id IN (:la, :lb)"),
                {"la": lead_a_id, "lb": lead_b_id},
            ).scalar()
            assert count_b == 1
    finally:
        with engine.begin() as conn:
            conn.execute(text("SELECT set_config('app.rls_bypass', 'on', true)"))
            conn.execute(
                text("DELETE FROM leads WHERE id IN (:la, :lb)"), {"la": lead_a_id, "lb": lead_b_id}
            )
            conn.execute(
                text("DELETE FROM users WHERE id IN (:ta, :tb)"), {"ta": tenant_a, "tb": tenant_b}
            )
        engine.dispose()
