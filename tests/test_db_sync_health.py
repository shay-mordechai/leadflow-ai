"""Regression tests for immutable-deployment database revision correlation."""

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.database.session import get_db
from src.routers.health import router


def _test_client(database: object) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: database
    return TestClient(app)


def test_db_sync_endpoint_returns_success_for_matching_revision(monkeypatch) -> None:
    """Schema/image correlation: matching expected and live Alembic revisions are healthy."""
    monkeypatch.setenv("EXPECTED_DB_REVISION", "revision_123")
    monkeypatch.setenv("CURRENT_IMAGE_SHA", "sha256:abc123")
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = "revision_123"

    response = _test_client(db).get("/health/db-sync-status")

    assert response.status_code == 200
    assert response.json() == {
        "is_synced": True,
        "image_sha": "sha256:abc123",
        "expected_revision": "revision_123",
        "actual_revision": "revision_123",
    }
    db.execute.assert_called_once()


def test_db_sync_endpoint_returns_503_for_revision_mismatch(monkeypatch) -> None:
    """Schema mismatch: the health probe must fail readiness when code expects another DB revision."""
    monkeypatch.setenv("EXPECTED_DB_REVISION", "revision_expected")
    monkeypatch.setenv("CURRENT_IMAGE_SHA", "sha256:running")
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = "revision_actual"

    response = _test_client(db).get("/health/db-sync-status")

    assert response.status_code == 503
    assert response.json() == {
        "is_synced": False,
        "image_sha": "sha256:running",
        "expected_revision": "revision_expected",
        "actual_revision": "revision_actual",
        "mismatch": {
            "expected": "revision_expected",
            "actual": "revision_actual",
        },
    }


def test_db_sync_endpoint_fails_closed_when_expected_revision_missing(monkeypatch) -> None:
    """Schema correlation: absent deployment metadata must never report an unverified DB as synchronized."""
    monkeypatch.delenv("EXPECTED_DB_REVISION", raising=False)
    monkeypatch.setenv("CURRENT_IMAGE_SHA", "sha256:running")
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = "revision_actual"

    response = _test_client(db).get("/health/db-sync-status")

    assert response.status_code == 503
    assert response.json()["is_synced"] is False
    assert response.json()["expected_revision"] is None
    assert response.json()["actual_revision"] == "revision_actual"


def test_db_sync_endpoint_fails_closed_when_revision_table_is_unavailable(
    monkeypatch,
) -> None:
    """Schema correlation: unavailable database metadata must return an explicit unhealthy status."""
    monkeypatch.setenv("EXPECTED_DB_REVISION", "revision_expected")
    monkeypatch.setenv("CURRENT_IMAGE_SHA", "sha256:running")
    db = MagicMock()
    db.execute.side_effect = RuntimeError("sensitive connection details")

    response = _test_client(db).get("/health/db-sync-status")

    assert response.status_code == 503
    assert response.json()["is_synced"] is False
    assert response.json()["reason"] == "database_revision_unavailable"
    assert "sensitive connection details" not in response.text


def test_health_route_is_registered_on_main_application() -> None:
    """Deployment health: the compatibility probe must be available on the application entry point."""
    from src.main import app

    assert "/health/db-sync-status" in app.openapi()["paths"]
