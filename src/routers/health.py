"""Health endpoints for runtime and database-schema compatibility checks."""

import logging
import os

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.database.session import get_db

router = APIRouter(tags=["System"])
logger = logging.getLogger("HealthChecks")


@router.get("/health/db-sync-status")
def database_sync_status(db: Session = Depends(get_db)) -> JSONResponse:
    """Compare the image's expected Alembic revision with the live database revision."""
    expected_revision = os.getenv("EXPECTED_DB_REVISION")
    image_sha = os.getenv("CURRENT_IMAGE_SHA")

    try:
        actual_revision = db.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one_or_none()
    except Exception as error:
        logger.error(
            "Database revision health check failed (%s)",
            type(error).__name__,
        )
        return JSONResponse(
            status_code=503,
            content={
                "is_synced": False,
                "image_sha": image_sha,
                "expected_revision": expected_revision,
                "actual_revision": None,
                "mismatch": {
                    "expected": expected_revision,
                    "actual": None,
                },
                "reason": "database_revision_unavailable",
            },
        )

    is_synced = (
        bool(expected_revision)
        and bool(image_sha)
        and actual_revision == expected_revision
    )
    payload = {
        "is_synced": is_synced,
        "image_sha": image_sha,
        "expected_revision": expected_revision,
        "actual_revision": actual_revision,
    }
    if not is_synced:
        payload["mismatch"] = {
            "expected": expected_revision,
            "actual": actual_revision,
        }
        if not expected_revision or not image_sha:
            payload["reason"] = "deployment_revision_metadata_missing"
        return JSONResponse(status_code=503, content=payload)

    return JSONResponse(status_code=200, content=payload)
