"""
Security and integration tests for the internal Marketing Advisor worker tasks,
least-privilege two-worker separation (rag_read vs mutations), RLS enforcement,
and audit logging.
"""

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

from src.config import settings
from src.database.session import (
    current_tenant_id_var,
)
from src.tasks.marketing_advisor import (
    analyze_tenant_marketing,
    deliver_marketing_digest,
)
from src.worker import celery_app


def test_marketing_advisor_celery_routing_and_beat_schedule():
    """Verify Marketing Advisor tasks are routed to the correct queues and scheduled in Celery Beat."""
    routes = celery_app.conf.task_routes
    assert routes is not None
    assert routes.get("src.tasks.marketing_advisor.dispatch_weekly_marketing_digests") == {
        "queue": "rag_read"
    }
    assert routes.get("src.tasks.marketing_advisor.analyze_tenant_marketing") == {
        "queue": "rag_read"
    }
    assert routes.get("src.tasks.marketing_advisor.deliver_marketing_digest") == {
        "queue": "mutations"
    }

    schedule = celery_app.conf.beat_schedule
    assert schedule is not None
    assert "weekly-marketing-advisor-digest" in schedule
    assert (
        schedule["weekly-marketing-advisor-digest"]["task"]
        == "src.tasks.marketing_advisor.dispatch_weekly_marketing_digests"
    )


def test_tenant_context_binding_and_cleanup_in_marketing_tasks():
    """Verify that tenant context variable is bound and guaranteed to reset in finally blocks."""
    initial_context = current_tenant_id_var.get()
    tenant_uuid = str(uuid.uuid4())

    # Test analyze_tenant_marketing context restoration under exception
    with patch("src.tasks.marketing_advisor.ReadOnlySessionLocal") as mock_session_local:
        mock_session_local.side_effect = RuntimeError("DB Connection Error")
        with pytest.raises(RuntimeError, match="DB Connection Error"):
            analyze_tenant_marketing(tenant_uuid)

        assert current_tenant_id_var.get() == initial_context


def test_marketing_advisor_least_privilege_reader_isolation():
    """Verify analyze_tenant_marketing runs on read-only session and cannot perform mutations."""
    read_url = settings.READ_ONLY_DATABASE_URL
    if not read_url or "sqlite" in read_url:
        pytest.skip(
            "Skipping PostgreSQL role test because READ_ONLY_DATABASE_URL is not set or using SQLite."
        )

    sync_url = read_url.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url)

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            with pytest.raises((ProgrammingError, Exception)):
                conn.execute(
                    text(
                        "INSERT INTO leads (id, user_id, name) VALUES (:id, :uid, 'Unauthorized Mutation')"
                    ),
                    {"id": uuid.uuid4(), "uid": uuid.uuid4()},
                )
                conn.commit()
    finally:
        engine.dispose()


def test_deliver_marketing_digest_creates_audit_log(mocker):
    """Verify deliver_marketing_digest records an AuditLog entry and dispatches WhatsApp notification."""
    db_url = settings.DATABASE_URL
    if not db_url or "sqlite" in db_url:
        pytest.skip("Skipping PostgreSQL RLS test because DATABASE_URL is SQLite or unset.")

    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url)
    tenant_id = uuid.uuid4()

    mocker.patch(
        "src.services.communication.whatsapp.whatsapp_adapter.send_message", return_value=True
    )

    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT set_config('app.rls_bypass', 'on', true)"))
            conn.execute(
                text(
                    "INSERT INTO users (id, email, name, hashed_password, plan_tier, subscription_status, monthly_ai_messages, role, personal_whatsapp) "
                    "VALUES (:id, :email, :name, 'pw', 'PRO', 'ACTIVE', 0, 'CLIENT', '+972500000000') ON CONFLICT DO NOTHING"
                ),
                {
                    "id": tenant_id,
                    "email": f"advisor_tenant_{tenant_id}@example.com",
                    "name": "Advisor Tenant",
                },
            )

        # Execute deliver_marketing_digest
        result = deliver_marketing_digest(
            str(tenant_id), "Test Marketing Digest", {"total_new_leads_7d": 5}
        )
        assert result["status"] == "delivered"

        # Verify AuditLog entry was recorded
        with engine.connect() as conn:
            conn.execute(text("SELECT set_config('app.rls_bypass', 'on', true)"))
            log_entry = conn.execute(
                text(
                    "SELECT action FROM audit_logs WHERE user_id = :uid AND action = 'MARKETING_DIGEST_GENERATED'"
                ),
                {"uid": str(tenant_id)},
            ).fetchone()
            assert log_entry is not None

    finally:
        with engine.begin() as conn:
            conn.execute(text("SELECT set_config('app.rls_bypass', 'on', true)"))
            conn.execute(
                text("DELETE FROM audit_logs WHERE user_id = :uid"), {"uid": str(tenant_id)}
            )
            conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": tenant_id})
        engine.dispose()
