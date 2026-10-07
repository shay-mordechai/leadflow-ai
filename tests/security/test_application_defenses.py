"""Regression tests for application-layer security controls."""

import asyncio
import threading

import pytest
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.middleware.request_limits import RequestBodyLimitMiddleware
from src.schemas.user import AISettingsSchema
from src.services.background_task_capacity import BackgroundTaskCapacity
from src.services.task_registry import _background_tasks, retain_task


def _limited_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        RequestBodyLimitMiddleware,
        max_body_size=1024,
        max_json_depth=16,
    )

    @app.post("/json")
    async def receive_json(request: Request) -> dict:
        return await request.json()

    return app


def test_json_request_body_size_is_bounded() -> None:
    """Vulnerability: Memory Exhaustion; oversized request bodies can exhaust worker memory."""
    response = TestClient(_limited_app()).post(
        "/json",
        content=b'{"data":"' + b"x" * 2048 + b'"}',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 413


def test_global_application_installs_body_limit_middleware() -> None:
    """Vulnerability: Large Payloads; the body cap must be active on the production application."""
    from src.main import app

    assert any(
        middleware.cls is RequestBodyLimitMiddleware
        for middleware in app.user_middleware
    )


def test_json_nesting_depth_is_bounded_before_parsing() -> None:
    """Vulnerability: JSON Deep-Nesting DoS; recursive JSON can crash parsers before schema validation."""
    nested_payload = b'{"a":' * 17 + b"0" + b"}" * 17
    response = TestClient(_limited_app()).post(
        "/json",
        content=nested_payload,
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "JSON nesting depth exceeds limit"


def test_audio_upload_retains_its_separate_body_limit() -> None:
    """Vulnerability: Large Payload Limits; the JSON cap must not break bounded audio uploads."""
    app = FastAPI()
    app.add_middleware(
        RequestBodyLimitMiddleware,
        max_body_size=16,
        max_multipart_body_size=64,
    )

    @app.post("/api/v1/sessions/upload/lead-id")
    async def receive_audio(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    response = TestClient(app).post(
        "/api/v1/sessions/upload/lead-id",
        content=b"x" * 32,
        headers={"content-type": "multipart/form-data; boundary=test"},
    )

    assert response.status_code == 200
    assert response.json()["size"] == 32


def test_update_schema_rejects_privileged_mass_assignment() -> None:
    """Vulnerability: Mass Assignment; attacker-supplied privilege fields must never enter settings updates."""
    with pytest.raises(ValidationError):
        AISettingsSchema.model_validate(
            {
                "business_name": "Example",
                "business_type": "Services",
                "is_admin": True,
            }
        )


def test_registration_schema_rejects_privileged_mass_assignment() -> None:
    """Vulnerability: Mass Assignment; registration must not accept caller-selected roles or plans."""
    from src.schemas.user import UserCreate

    with pytest.raises(ValidationError):
        UserCreate.model_validate(
            {
                "email": "user@example.com",
                "full_name": "Example User",
                "business_type": "Services",
                "password": "ValidPassword123",
                "plan_tier": "PRO",
                "is_admin": True,
            }
        )


def test_campaign_phone_validation_rejects_long_regex_bomb_input() -> None:
    """Vulnerability: ReDoS; adversarial phone strings must be rejected by a bounded-time pattern."""
    from src.routers.webhooks.campaign import InboundLeadPayload

    with pytest.raises(ValidationError):
        InboundLeadPayload(
            lead_name="Example",
            phone_number="+" + "9" * 100_000 + "!",
            campaign_source="test",
        )


def test_lead_pagination_limit_is_enforced_by_fastapi() -> None:
    """Vulnerability: Unbounded Pagination DoS; API callers cannot request an excessive page size."""
    from src.database.session import get_db
    from src.routers import leads
    from src.security.dependencies import get_current_user

    app = FastAPI()
    app.state.limiter = leads.limiter
    app.include_router(leads.router, prefix="/leads")
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[get_current_user] = lambda: type(
        "UserStub",
        (),
        {"id": "user-id", "email": "user@example.com"},
    )()

    response = TestClient(app).get("/leads/?limit=101")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_background_task_capacity_rejects_excess_work() -> None:
    """Vulnerability: Background Task Memory Exhaustion; in-flight task queues must have a hard bound."""
    capacity = BackgroundTaskCapacity(max_in_flight=1)
    first_tasks = BackgroundTasks()
    second_tasks = BackgroundTasks()

    async def process(_: dict[str, str]) -> None:
        await asyncio.sleep(0)

    assert capacity.try_add(first_tasks, process, {"id": "first"})
    assert not capacity.try_add(second_tasks, process, {"id": "second"})
    await first_tasks()
    assert capacity.try_add(second_tasks, process, {"id": "second"})


@pytest.mark.asyncio
async def test_retained_task_registry_holds_tasks_until_completion() -> None:
    """Vulnerability: Silent Task Garbage Collection; scheduled coroutines need strong references until done."""
    event = asyncio.Event()

    async def wait_for_release() -> None:
        await event.wait()

    task = asyncio.create_task(wait_for_release())
    retain_task(task)
    assert task in _background_tasks

    event.set()
    await task
    await asyncio.sleep(0)
    assert task not in _background_tasks


def test_login_password_verification_runs_off_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vulnerability: Event Loop Starvation; synchronous BCrypt verification must run in a worker thread."""
    from src.routers import auth
    from src.database.session import get_db

    main_thread_id = threading.get_ident()

    class Query:
        def filter(self, *_: object) -> "Query":
            return self

        def first(self) -> object:
            return type(
                "UserStub",
                (),
                {
                    "hashed_password": "stored",
                    "is_active": True,
                    "email": "user@example.com",
                    "otp_code": None,
                    "otp_expires_at": None,
                },
            )()

    class Database:
        def query(self, *_: object) -> Query:
            return Query()

        def commit(self) -> None:
            pass

    def verify_on_worker_thread(_: str, __: str) -> bool:
        assert threading.get_ident() != main_thread_id
        return True

    monkeypatch.setattr(auth, "verify_hash", verify_on_worker_thread)
    monkeypatch.setattr(auth, "send_otp_email", lambda *_: None)
    app = FastAPI()
    app.state.limiter = auth.limiter
    app.include_router(auth.router, prefix="/auth")
    app.dependency_overrides[get_db] = Database

    response = TestClient(app).post(
        "/auth/login",
        data={"username": "user@example.com", "password": "ValidPassword123"},
    )

    assert response.status_code == 200
    assert response.json()["mfa_required"] is True
