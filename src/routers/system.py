# src/routers/system.py
import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.database.session import get_db
from src.config import settings
import redis

router = APIRouter(prefix="/api/v1/system", tags=["System & Health"])
logger = logging.getLogger("SystemHealth")

@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """
    Comprehensive system health check.
    Verifies Database (PostgreSQL/SQLite), Redis broker, and storage mount.
    """
    health_status = {
        "status": "healthy",
        "database": "unhealthy",
        "redis": "unhealthy",
        "storage": "unhealthy"
    }
    
    # 1. Check Database connection
    try:
        db.execute(text("SELECT 1"))
        health_status["database"] = "healthy"
    except Exception as e:
        logger.error(f"Health check failed [Database]: {e}")
        health_status["status"] = "degraded"

    # 2. Check Redis connection
    try:
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        health_status["redis"] = "healthy"
    except Exception as e:
        logger.error(f"Health check failed [Redis]: {e}")
        health_status["status"] = "degraded"

    # 3. Check Local Storage path writability
    try:
        storage_path = getattr(settings, 'STORAGE_BASE_PATH', '/app/storage')
        if os.access(storage_path, os.W_OK):
            health_status["storage"] = "healthy"
        else:
            health_status["status"] = "degraded"
    except Exception as e:
        logger.error(f"Health check failed [Storage]: {e}")
        health_status["status"] = "degraded"

    if health_status["status"] != "healthy":
        return status.HTTP_503_SERVICE_UNAVAILABLE, health_status

    return health_status