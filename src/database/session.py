# src/database/session.py
import logging
import uuid
from collections.abc import Generator
from contextvars import ContextVar, Token

import sqlalchemy.exc
from sqlalchemy import Column, Engine, ForeignKey, create_engine, event, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, declarative_base, declared_attr, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import CHAR, TypeDecorator
from tenacity import before_log, retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from src.config import settings

logger = logging.getLogger("LeadFlowSystem")

# --- ContextVar for PostgreSQL RLS Tenant Context ---
current_tenant_id_var: ContextVar[str | None] = ContextVar("current_tenant_id", default=None)


def set_current_tenant_context(tenant_id: str | None) -> Token[str | None]:
    """Bind the active tenant UUID to the current execution context."""
    return current_tenant_id_var.set(tenant_id)


def reset_current_tenant_context(token: Token[str | None]) -> None:
    """Restore the previous tenant context using the token from set_current_tenant_context."""
    current_tenant_id_var.reset(token)


# --- 1. Platform-Independent GUID Type ---
class GUID(TypeDecorator):
    """Store UUIDs natively on PostgreSQL and as 32-char hex strings on SQLite."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID

            return dialect.type_descriptor(UUID())
        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        parsed = value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        if dialect.name == "postgresql":
            return str(parsed)
        return f"{parsed.int:032x}"

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


# --- 2. Declarative Base ---
Base = declarative_base()


# --- 3. Database URL Normalization & Engine Builders ---
def _build_sync_url(raw_url: str) -> URL:
    """Normalize a database URL for synchronous SQLAlchemy engines."""
    url = make_url(raw_url)
    if url.drivername in {"sqlite", "sqlite+pysqlite", "sqlite+aiosqlite"}:
        url = url.set(drivername="sqlite")
        if url.database == ":memory:" and "cache" not in url.query:
            url = url.update_query_dict({"cache": "shared"})
        return url
    if url.drivername in {"postgres", "postgresql", "postgresql+psycopg2", "postgresql+asyncpg"}:
        return url.set(drivername="postgresql+psycopg2")
    raise ValueError(f"Unsupported sync database driver: {url.drivername}")


def _build_async_url(raw_url: str) -> URL:
    """Normalize a database URL for asynchronous SQLAlchemy engines."""
    url = make_url(raw_url)
    if url.drivername in {"sqlite", "sqlite+pysqlite", "sqlite+aiosqlite"}:
        url = url.set(drivername="sqlite+aiosqlite")
        if url.database == ":memory:" and "cache" not in url.query:
            url = url.update_query_dict({"cache": "shared"})
        return url
    if url.drivername in {"postgres", "postgresql", "postgresql+psycopg2", "postgresql+asyncpg"}:
        return url.set(drivername="postgresql+asyncpg")
    raise ValueError(f"Unsupported async database driver: {url.drivername}")


def _create_sync_engine(raw_url: str) -> Engine:
    """Create a configured synchronous engine for PostgreSQL or SQLite."""
    sync_url = _build_sync_url(raw_url)
    is_sqlite = sync_url.drivername.startswith("sqlite")

    engine_kwargs: dict = {
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }

    if is_sqlite:
        engine_kwargs["connect_args"] = {"uri": True, "check_same_thread": False}
        if sync_url.database == ":memory:":
            engine_kwargs["poolclass"] = StaticPool
    else:
        # Bounded pool prevents exhausting PostgreSQL max_connections across multiple workers.
        engine_kwargs.update({"pool_size": 5, "max_overflow": 10, "pool_timeout": 30})

    created_engine = create_engine(sync_url, **engine_kwargs)

    if is_sqlite:

        @event.listens_for(created_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            # Enable Write-Ahead Logging (WAL) to reduce lock contention in SQLite test runs.
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return created_engine


# --- Primary Read/Write Engine & Session ---
engine = _create_sync_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Least-Privilege Read-Only Engine & Session ---
_read_only_raw_url = (settings.READ_ONLY_DATABASE_URL or "").strip()
if _read_only_raw_url and _read_only_raw_url != settings.DATABASE_URL:
    readonly_engine = _create_sync_engine(_read_only_raw_url)
else:
    readonly_engine = engine

ReadOnlySessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=readonly_engine)

# --- Asynchronous Engine & Session ---
async_database_url = _build_async_url(settings.DATABASE_URL)
async_engine_kwargs: dict = {
    "pool_pre_ping": True,
    "pool_recycle": 1800,
}

if async_database_url.drivername.startswith("sqlite"):
    async_engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    async_engine_kwargs.update({"pool_size": 5, "max_overflow": 10, "pool_timeout": 30})

async_engine = create_async_engine(async_database_url, **async_engine_kwargs)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# --- 4. PostgreSQL RLS Transaction Enforcement ---
@event.listens_for(Session, "after_begin")
def _apply_rls_tenant_context(session, transaction, connection) -> None:
    """Apply transaction-local PostgreSQL RLS tenant context on every session begin.

    Registered on sqlalchemy.orm.Session so it covers SessionLocal, ReadOnlySessionLocal,
    and AsyncSessionLocal (via SQLAlchemy's sync greenlet bridge). Using is_local=true
    guarantees the setting resets at COMMIT/ROLLBACK and never leaks across pooled connections.
    """
    tenant_id = current_tenant_id_var.get()
    if not tenant_id or connection.dialect.name != "postgresql":
        return

    try:
        parsed_uuid = str(uuid.UUID(tenant_id))
    except (ValueError, TypeError) as exc:
        logger.warning("Invalid tenant_id format in RLS context: %s", exc)
        return

    connection.execute(
        text("SELECT set_config('app.current_tenant_id', :tid, true)"),
        {"tid": parsed_uuid},
    )


@retry(
    stop=stop_after_attempt(5),
    wait=wait_fixed(2),
    before=before_log(logger, logging.WARNING),
    retry=retry_if_exception_type((sqlalchemy.exc.OperationalError, ConnectionRefusedError)),
    reraise=True,
)
async def verify_db_connection() -> None:
    """Verify database connectivity on startup with tenacity retries."""
    async with async_engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("Database connection verified successfully.")


# --- 5. FastAPI Database Dependencies ---
def get_db() -> Generator[Session, None, None]:
    """Yield a read/write database session scoped to the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_readonly_db() -> Generator[Session, None, None]:
    """Yield a least-privilege read-only database session scoped to the request."""
    db = ReadOnlySessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- 6. Tenant Mixin ---
class TenantAwareMixin:
    """Mixin adding a non-nullable, indexed tenant foreign key to tenant-scoped models."""

    @declared_attr
    def tenant_id(cls):
        return Column(GUID(), ForeignKey("tenants.id"), nullable=False, index=True)
