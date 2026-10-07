"""Category 5 security regression tests for identity and data handling."""

import base64
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException, Response
from fastapi.testclient import TestClient
from jose import jwt
from starlette.datastructures import UploadFile

from src.config import settings
from src.database.session import get_db
from src.routers import auth, sessions
from src.security import dependencies
from src.security.dependencies import get_current_user
from src.security.audit import AuditService
from src.services.communication import email as email_module


def _unsigned_jwt(claims: dict[str, object]) -> str:
    encode_segment = lambda value: base64.urlsafe_b64encode(  # noqa: E731
        json.dumps(value, separators=(",", ":"), default=lambda item: int(item.timestamp())).encode()
    ).rstrip(b"=").decode()
    return f"{encode_segment({'alg': 'none', 'typ': 'JWT'})}.{encode_segment(claims)}."


def test_auth_token_has_unique_id_and_fixed_hs256_algorithm() -> None:
    """Vulnerability: Stateless JWT Revocation; tokens need unique identifiers for targeted revocation."""
    token = auth.create_access_token({"sub": "user-123", "email": "user@example.com"})
    header = jwt.get_unverified_header(token)
    claims = jwt.get_unverified_claims(token)

    assert header["alg"] == "HS256"
    assert claims.get("jti")


@pytest.mark.asyncio
@pytest.mark.parametrize("algorithm", ["none", "HS384"])
async def test_current_user_rejects_jwt_algorithm_downgrade(algorithm: str) -> None:
    """Vulnerability: JWT Downgrade Attack; unsigned or non-HS256 tokens must not authenticate."""
    claims = {
        "sub": "user@example.com",
        "email": "user@example.com",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        "jti": str(uuid.uuid4()),
        "token_version": 0,
    }
    token = (
        _unsigned_jwt(claims)
        if algorithm == "none"
        else jwt.encode(claims, settings.SECRET_KEY, algorithm=algorithm)
    )

    class Database:
        def query(self, *_: object) -> object:
            raise AssertionError("Rejected tokens must not trigger database lookup")

    with pytest.raises(HTTPException) as error:
        await get_current_user(token=token, db=Database())  # type: ignore[arg-type]
    assert getattr(error.value, "status_code", None) == 401


@pytest.mark.asyncio
async def test_redis_blocklist_rejects_revoked_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vulnerability: Stateless JWT Revocation; a Redis-blocklisted bearer token must fail immediately."""
    from src.security import token_revocation

    token = auth.create_access_token({"sub": "user@example.com"})
    redis = MagicMock()
    redis.set = AsyncMock(return_value=True)
    redis.exists = AsyncMock(return_value=1)
    monkeypatch.setattr(token_revocation, "redis_client", redis)

    await token_revocation.revoke_token(token)

    with pytest.raises(HTTPException) as error:
        await token_revocation.ensure_token_not_revoked(token)
    assert getattr(error.value, "status_code", None) == 401
    redis.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_logout_revokes_the_presented_bearer_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vulnerability: Stateless JWT Revocation; logout must add the active token to the blocklist."""
    revoker = AsyncMock()
    monkeypatch.setattr(auth, "revoke_token", revoker)
    token = auth.create_access_token({"sub": "user@example.com"})

    await auth.logout(Response(), token)

    revoker.assert_awaited_once_with(token)


@pytest.mark.asyncio
async def test_tokens_from_before_password_change_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vulnerability: Stolen JWT after password change; auth-version mismatch must revoke earlier sessions."""
    from src.security import token_revocation

    token = jwt.encode(
        {
            "sub": "user@example.com",
            "email": "user@example.com",
            "jti": str(uuid.uuid4()),
            "token_version": 2,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    monkeypatch.setattr(
        dependencies,
        "ensure_token_not_revoked",
        AsyncMock(return_value=None),
    )

    class Query:
        def filter(self, *_: object) -> "Query":
            return self

        def first(self) -> object:
            return SimpleNamespace(
                email="user@example.com",
                token_version=3,
            )

    class Database:
        def query(self, *_: object) -> Query:
            return Query()

    with pytest.raises(HTTPException) as error:
        await get_current_user(token=token, db=Database())  # type: ignore[arg-type]
    assert getattr(error.value, "status_code", None) == 401


def test_audit_log_strips_line_breaks_ansi_and_control_sequences(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Vulnerability: Log Injection; untrusted CR/LF and terminal controls must not forge audit records."""
    db = MagicMock()
    caplog.set_level(logging.INFO, logger="AuditSystem")
    hostile_action = "lead.updated\r\n[CRITICAL]\x1b[31m forged"

    AuditService.log(db, "user-1", hostile_action, {"note": "safe\nforged"})

    record = next(record for record in caplog.records if record.name == "AuditSystem")
    assert "\r" not in record.getMessage()
    assert "\n" not in record.getMessage()
    assert "\x1b" not in record.getMessage()
    assert "\r" not in db.add.call_args.args[0].action
    assert "\n" not in db.add.call_args.args[0].details["note"]
    assert "\r" not in record.user_id


@pytest.mark.asyncio
async def test_error_email_escapes_untrusted_html(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vulnerability: SSTI and HTML Injection; untrusted error/request values must render as escaped text."""
    service = email_module.EmailService()
    service.conf = object()
    sent_messages: list[object] = []

    class Mailer:
        def __init__(self, _: object) -> None:
            pass

        async def send_message(self, message: object) -> None:
            sent_messages.append(message)

    monkeypatch.setattr(email_module, "FastMail", Mailer)
    monkeypatch.setattr(email_module.settings, "ADMIN_EMAIL", "admin@example.com")

    await service.send_error_alert_email(
        error_summary="<script>alert(1)</script>",
        stack_trace="<img src=x onerror=alert(1)>",
        request_info={"url": "<svg/onload=alert(1)>"},
    )

    body = sent_messages[0].body  # type: ignore[attr-defined]
    assert "<script>" not in body
    assert "<img" not in body
    assert "<svg" not in body
    assert "&lt;script&gt;" in body


def test_audio_upload_uses_mime_derived_extension_and_contained_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Vulnerability: Malicious Media Path Traversal; untrusted filenames must not control stored paths."""
    user_id = uuid.uuid4()
    media_root = tmp_path / "audio"
    monkeypatch.setattr(sessions, "UPLOAD_DIR", str(media_root))
    monkeypatch.setattr(sessions.magic, "from_buffer", lambda _data, mime=True: "audio/wav")
    monkeypatch.setattr(sessions.process_meeting_audio, "delay", MagicMock())

    class Query:
        def filter(self, *_: object) -> "Query":
            return self

        def first(self) -> object:
            return SimpleNamespace(id="lead-1", user_id=user_id)

    class Database:
        def query(self, *_: object) -> Query:
            return Query()

        def add(self, _: object) -> None:
            pass

        def commit(self) -> None:
            pass

        def refresh(self, _: object) -> None:
            pass

    app = FastAPI()
    app.include_router(sessions.router)
    app.dependency_overrides[get_db] = Database
    app.dependency_overrides[dependencies.get_current_user] = lambda: SimpleNamespace(
        id=user_id,
        email="user@example.com",
    )
    try:
        response = TestClient(app).post(
            "/upload/lead-1",
            files={
                "file": (
                    "../../outside.html",
                    b"valid wav bytes",
                    "audio/wav",
                )
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    stored_path = (media_root / str(user_id) / response.json()["filename"]).resolve()
    assert stored_path.is_relative_to((media_root / str(user_id)).resolve())
    assert stored_path.suffix == ".wav"
    assert stored_path.read_bytes() == b"valid wav bytes"


@pytest.mark.asyncio
async def test_local_transcription_rejects_paths_outside_upload_storage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Vulnerability: Malicious Media Processing; user-controlled paths must never reach the local parser."""
    from src.services.ai import whisper

    service = whisper.WhisperService()
    monkeypatch.setattr(whisper, "LOCAL_AUDIO_ROOT", tmp_path / "audio")
    parser = MagicMock()
    monkeypatch.setattr(service, "_transcribe_sync", parser)

    result = await service.transcribe_local_file(str(tmp_path / "outside.wav"))

    assert result == "[Error: Invalid media path]"
    parser.assert_not_called()


@pytest.mark.asyncio
async def test_remote_audio_transcriber_does_not_fetch_internal_or_untrusted_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vulnerability: Malicious Media Processing; arbitrary webhook media URLs must not reach the network."""
    from src.services.ai import whisper

    service = whisper.WhisperService()
    parser = MagicMock(return_value="transcribed")
    monkeypatch.setattr(service, "_transcribe_sync", parser)
    requests: list[str] = []

    class FakeClient:
        def __init__(self, **_: object) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            pass

        async def get(self, url: str) -> object:
            requests.append(url)
            return SimpleNamespace(status_code=200, content=b"audio")

    monkeypatch.setattr(whisper.httpx, "AsyncClient", FakeClient)

    await service.transcribe_from_url("http://127.0.0.1/latest/meta-data/")

    assert not requests
    parser.assert_not_called()


@pytest.mark.asyncio
async def test_remote_audio_transcriber_rejects_unapproved_content_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vulnerability: Malicious Media Processing; remote downloads must be audio MIME types, not active content."""
    from src.services.ai import whisper

    service = whisper.WhisperService()
    parser = MagicMock(return_value="transcribed")
    monkeypatch.setattr(service, "_transcribe_sync", parser)

    class Response:
        headers = {"content-type": "text/html"}

        async def __aenter__(self) -> "Response":
            return self

        async def __aexit__(self, *_: object) -> None:
            pass

        def raise_for_status(self) -> None:
            pass

        async def aiter_bytes(self):
            yield b"<html>not audio</html>"

    class Client:
        def __init__(self, **_: object) -> None:
            pass

        async def __aenter__(self) -> "Client":
            return self

        async def __aexit__(self, *_: object) -> None:
            pass

        def stream(self, *_: object) -> Response:
            return Response()

    monkeypatch.setattr(whisper.httpx, "AsyncClient", Client)

    result = await service.transcribe_from_url("https://api.twilio.com/media/1")

    assert result == "[Error: Could not transcribe audio from URL]"
    parser.assert_not_called()


@pytest.mark.asyncio
async def test_remote_audio_transcriber_enforces_streaming_size_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vulnerability: Media Memory Exhaustion; streamed provider media must stop at the configured byte ceiling."""
    from src.services.ai import whisper

    monkeypatch.setattr(whisper, "MAX_REMOTE_AUDIO_SIZE", 4)
    service = whisper.WhisperService()
    parser = MagicMock(return_value="transcribed")
    monkeypatch.setattr(service, "_transcribe_sync", parser)

    class Response:
        headers = {"content-type": "audio/ogg"}

        async def __aenter__(self) -> "Response":
            return self

        async def __aexit__(self, *_: object) -> None:
            pass

        def raise_for_status(self) -> None:
            pass

        async def aiter_bytes(self):
            yield b"12345"

    class Client:
        def __init__(self, **_: object) -> None:
            pass

        async def __aenter__(self) -> "Client":
            return self

        async def __aexit__(self, *_: object) -> None:
            pass

        def stream(self, *_: object) -> Response:
            return Response()

    monkeypatch.setattr(whisper.httpx, "AsyncClient", Client)

    result = await service.transcribe_from_url("https://api.twilio.com/media/1")

    assert result == "[Error: Could not transcribe audio from URL]"
    parser.assert_not_called()


@pytest.mark.asyncio
async def test_audio_upload_rejects_disallowed_detected_media_type(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Vulnerability: Malicious Media Processing; unapproved magic-byte MIME types must never be persisted."""
    monkeypatch.setattr(sessions, "UPLOAD_DIR", str(tmp_path / "audio"))
    monkeypatch.setattr(
        sessions.magic,
        "from_buffer",
        lambda _data, mime=True: "application/x-executable",
    )

    class Query:
        def filter(self, *_: object) -> "Query":
            return self

        def first(self) -> object:
            return SimpleNamespace(id="lead-1", user_id="user-1")

    db = MagicMock()
    db.query.return_value = Query()

    with pytest.raises(HTTPException) as error:
        await sessions.upload_audio(
            lead_id="lead-1",
            file=UploadFile(filename="voice.wav", file=BytesIO(b"not audio")),
            db=db,
            current_user=SimpleNamespace(id="user-1", email="user@example.com"),  # type: ignore[arg-type]
        )

    assert getattr(error.value, "status_code", None) == 415
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_mock_auth_emails_do_not_log_one_time_codes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Vulnerability: Secret Exposure; fallback auth-email logs must not disclose one-time codes."""
    service = email_module.EmailService()
    service.conf = None
    caplog.set_level(logging.INFO, logger="EmailService")

    await service.send_otp_email("user@example.com", "681204")
    await service.send_password_reset_email("user@example.com", "927153")

    assert "681204" not in caplog.text
    assert "927153" not in caplog.text


@pytest.mark.asyncio
async def test_audio_upload_rejects_oversized_payload_before_persisting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vulnerability: Malicious Media Processing; size limits must reject input before storage or parsing."""
    monkeypatch.setattr(sessions, "MAX_FILE_SIZE", 8)
    file = UploadFile(
        filename="recording.wav",
        file=BytesIO(b"123456789"),
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        id="lead-1",
        user_id="user-1",
    )

    with pytest.raises(HTTPException) as error:
        await sessions.upload_audio(
            lead_id="lead-1",
            file=file,
            db=db,
            current_user=SimpleNamespace(id="user-1", email="user@example.com"),  # type: ignore[arg-type]
        )

    assert error.value.status_code == 413
    db.add.assert_not_called()
