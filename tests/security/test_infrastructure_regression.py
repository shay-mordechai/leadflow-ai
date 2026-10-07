"""Category 6 baseline posture tests for configuration and deployment."""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from src.config import Settings, settings, validate_config
from src.database.models import Lead, MediaInteraction, Message, User
from src.database.session import Base, get_db
from src.routers import auth, sessions
from src.security import dependencies
from src.tasks import retention_tasks


def test_production_configuration_rejects_disk_env_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Vulnerability: In-Memory Secrets; production must not load secrets from a disk .env file."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("SECRET_KEY=must-not-be-read", encoding="utf-8")

    with pytest.raises(ValueError, match="\\.env"):
        validate_config(Settings(APP_ENV="production", SECRET_KEY="s" * 48))


def test_production_configuration_rejects_default_or_short_secret(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Vulnerability: Weak Secret Bootstrap; production must require a strong external signing secret."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="SECRET_KEY"):
        validate_config(Settings(APP_ENV="production", SECRET_KEY="temporary_dev_key"))


def test_production_configuration_accepts_external_secret_without_env_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Vulnerability: In-Memory Secrets; production configuration must support environment-injected secrets."""
    monkeypatch.chdir(tmp_path)

    validate_config(Settings(APP_ENV="production", SECRET_KEY="secure-production-key-" * 3))


def test_otp_consumption_is_atomic_and_single_use() -> None:
    """Vulnerability: MFA OTP Replay; only one competing verification may consume a valid OTP."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    db: Session = session_factory()
    try:
        user = User(
            id=uuid.uuid4(),
            email="otp@example.com",
            name="OTP User",
            hashed_password="unused",
        )
        user.otp_code = "123456"
        user.otp_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=5)
        db.add(user)
        db.commit()
        db.refresh(user)
        stale_user_snapshot = SimpleNamespace(
            id=user.id,
            _otp_encrypted=user._otp_encrypted,
            otp_expires_at=user.otp_expires_at,
        )

        assert auth.consume_otp_once(db, stale_user_snapshot)
        assert not auth.consume_otp_once(db, stale_user_snapshot)
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_protected_audio_route_returns_not_found_for_another_tenants_lead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vulnerability: IDOR; the route must scope lead lookup to the authenticated tenant."""
    class Query:
        def filter(self, *_: object) -> "Query":
            return self

        def first(self) -> None:
            return None

    class Database:
        def query(self, *_: object) -> Query:
            return Query()

    app = FastAPI()
    app.include_router(sessions.router)
    app.dependency_overrides[get_db] = Database
    app.dependency_overrides[dependencies.get_current_user] = lambda: SimpleNamespace(
        id="tenant-a",
        email="a@example.com",
    )
    try:
        response = TestClient(app).post(
            "/upload/another-tenants-lead",
            files={"file": ("audio.wav", b"audio", "audio/wav")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_global_exception_response_hides_stack_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vulnerability: Stack Trace Leakage; unexpected exceptions return only generic client-safe details."""
    from src import main

    monkeypatch.setattr(main, "retain_task", lambda task: task.cancel())
    monkeypatch.setattr(main.email_service, "send_error_alert_email", AsyncMock())

    test_app = FastAPI()
    test_app.add_exception_handler(Exception, main.global_exception_handler)

    @test_app.get("/test/security-error-response")
    async def raise_internal_error() -> None:
        raise RuntimeError("STACK_TRACE_SENTINEL")

    response = TestClient(test_app, raise_server_exceptions=False).get(
        "/test/security-error-response"
    )

    assert response.status_code == 500
    assert "STACK_TRACE_SENTINEL" not in response.text
    assert "Traceback" not in response.text
    assert response.json()["error"]


def _request(peer: str, headers: list[tuple[bytes, bytes]]) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers,
            "query_string": b"",
            "server": ("testserver", 80),
            "client": (peer, 12345),
            "scheme": "http",
        }
    )


def test_rate_limit_uses_valid_cloudflare_ip_only_from_trusted_peer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vulnerability: Proxy IP Spoofing; forwarded client IPs are trusted only from configured proxies."""
    from src.security.rate_limiter import get_real_ip

    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", ["127.0.0.1"], raising=False)
    headers = [(b"cf-connecting-ip", b"198.51.100.27")]

    assert get_real_ip(_request("127.0.0.1", headers)) == "198.51.100.27"
    assert get_real_ip(_request("203.0.113.4", headers)) == "203.0.113.4"


def test_rate_limit_rejects_malformed_forwarded_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vulnerability: Proxy IP Spoofing; malformed proxy headers must fall back to the socket peer."""
    from src.security.rate_limiter import get_real_ip

    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", ["127.0.0.1"], raising=False)

    assert get_real_ip(
        _request("127.0.0.1", [(b"cf-connecting-ip", b"198.51.100.27, 127.0.0.1")])
    ) == "127.0.0.1"


def test_retention_policy_is_ninety_days_and_deletes_expired_leads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vulnerability: Excessive Personal Data Retention; leads beyond 90 days must be deleted."""
    monkeypatch.setattr(settings, "RETENTION_TTL_HOURS", 90 * 24)
    cutoff = retention_tasks._retention_cutoff()
    age = datetime.now(timezone.utc).replace(tzinfo=None) - cutoff
    assert timedelta(days=89, hours=23) <= age <= timedelta(days=90, minutes=1)

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    db: Session = session_factory()
    try:
        user = User(
            id=uuid.uuid4(),
            email="retention@example.com",
            name="Retention User",
            hashed_password="unused",
        )
        db.add(user)
        db.flush()
        lead = Lead(
            id=uuid.uuid4(),
            user_id=user.id,
            name="Expired lead",
            created_at=cutoff - timedelta(seconds=1),
        )
        lead_id = lead.id
        db.add(lead)
        db.commit()
        db.add(
            Message(
                lead_id=lead_id,
                sender_type="user",
                content="Retained personal message",
            )
        )
        db.add(
            MediaInteraction(
                user_id=user.id,
                lead_id=lead_id,
                file_path="outside-retention-root.wav",
                message_text="Retained media metadata",
            )
        )
        db.commit()

        assert retention_tasks._purge_expired_leads(db, cutoff) == 1
        assert db.query(Lead).filter(Lead.id == lead_id).first() is None
        assert db.query(Message).filter(Message.lead_id == lead_id).count() == 0
        assert db.query(MediaInteraction).filter(MediaInteraction.lead_id == lead_id).count() == 0
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_retention_cleanup_is_scheduled_hourly() -> None:
    """Vulnerability: Stale Personal Data; automated cleanup must run on the Celery beat schedule."""
    from src.worker import celery_app

    schedule = celery_app.conf.beat_schedule
    assert "purge-expired-tenant-data" in schedule
    assert schedule["purge-expired-tenant-data"]["schedule"].minute == {0}


def test_container_disables_core_dumps() -> None:
    """Vulnerability: Core Dump Secret Exposure; deployment containers must disable core dumps."""
    from pathlib import Path

    compose = Path("compose.yaml").read_text(encoding="utf-8")
    assert "ulimits:" in compose
    assert "core:" in compose
    assert "0" in compose.split("core:", 1)[1].splitlines()[0]


def test_ci_workflow_runs_trivy_and_gitleaks() -> None:
    """Vulnerability: CI Supply-Chain and Secret Exposure; workflows must scan source and container inputs."""
    from pathlib import Path

    workflow = Path(".github/workflows/production.yml").read_text(encoding="utf-8").lower()
    assert "trivy" in workflow
    assert "gitleaks" in workflow


def test_backend_deployment_filters_include_migration_and_backup_changes() -> None:
    """CI deployment coverage: migration and backup changes must trigger backend rebuilds."""
    from pathlib import Path

    workflow = Path(".github/workflows/production.yml").read_text(encoding="utf-8")
    for path in ("alembic/**", "alembic.ini", "scripts/**", ".gitleaks.toml"):
        assert f"'{path}'" in workflow


def test_wasm_toolchain_and_build_are_conditional_on_data_gate_changes() -> None:
    """CI efficiency: Rust setup and WASM compilation run only for relevant deployment events."""
    from pathlib import Path

    workflow = Path(".github/workflows/production.yml").read_text(encoding="utf-8")
    condition = "if: needs.detect-changes.outputs.datagate == 'true' || github.event_name == 'workflow_dispatch'"
    steps = workflow.split("- name:")
    rust_steps = [step for step in steps if "Install Rust Toolchain (WASM)" in step or "Build WASM Filter" in step]
    assert len(rust_steps) == 2
    assert all(condition in step for step in rust_steps)


def test_backend_image_receives_current_commit_sha() -> None:
    """Immutable deployments: runtime compatibility checks need the build's source SHA."""
    from pathlib import Path

    workflow = Path(".github/workflows/production.yml").read_text(encoding="utf-8")
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert "--build-arg CURRENT_IMAGE_SHA=${{ github.sha }}" in workflow
    assert "ARG CURRENT_IMAGE_SHA" in dockerfile
    assert "ENV CURRENT_IMAGE_SHA=${CURRENT_IMAGE_SHA}" in dockerfile


def test_gitleaks_allowlists_are_limited_to_known_false_positives() -> None:
    """Secret scanning: only the historical commit and explicit UI placeholders are allowlisted."""
    from pathlib import Path

    config = Path(".gitleaks.toml").read_text(encoding="utf-8")
    dashboard = Path("frontend/app/dashboard/marketer/page.tsx").read_text(encoding="utf-8")
    assert "[extend]\nuseDefault = true" in config
    assert "5be64ff630c16b659b6e82fafd24e9d59986e175" in config
    assert "frontend/app/dashboard/marketer/page\\.tsx" in config
    assert "YOUR_CAMPAIGN_API_KEY_[12]" in config
    assert "Legacy mock API key literals" in config
    assert "YOUR_CAMPAIGN_API_KEY_1" in dashboard
    assert "YOUR_CAMPAIGN_API_KEY_2" in dashboard
    assert "ml_live_" not in dashboard
