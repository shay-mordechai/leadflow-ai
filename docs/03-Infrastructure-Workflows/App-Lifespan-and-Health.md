
# Application Lifespan, Health Checks & Worker Queues

## FastAPI Lifespan (`src/main.py`)

1. **Startup:** Validates typed Pydantic settings (`src/config.py`), initializes async SQLAlchemy connection pools, verifies Redis reachability, and registers `RequestBodyLimitMiddleware` and tenant context listeners.
2. **Shutdown:** Gracefully drains in-flight background tasks within `BoundedSemaphore(200)` and disposes database/Redis pools cleanly on `SIGTERM` during Quadlet rolling restarts.

## Health & Readiness Endpoints

* `GET /health` — Lightweight liveness probe for container healthchecks.
* `GET /health/db-sync-status` — Verifies PostgreSQL connectivity and compares live `alembic_version` against codebase migration head (checked automatically post-deploy).

## Celery Worker & Beat Topology

* **`leadflow-worker`:** Executes asynchronous post-ingestion tasks, failed delivery retries, and Whisper audio transcriptions (planned split into `-Q realtime_chat` and `-Q audio_queue` so 15MB voice notes cannot delay text replies).
* **`leadflow-beat`:** Must strictly run with **1 replica** in production to prevent duplicate 5-minute `ProductionWatchdog` checks, duplicate follow-up dispatches, or double 90-day GDPR retention purges.
