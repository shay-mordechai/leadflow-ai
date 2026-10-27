# src/database/session.py
import uuid

from sqlalchemy import Column, ForeignKey, create_engine, event, text
import sqlalchemy.exc
import logging
from tenacity import retry, stop_after_attempt, wait_fixed, before_log, retry_if_exception_type
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, declared_attr, sessionmaker
from sqlalchemy.types import CHAR, TypeDecorator

from src.config import settings


# --- 1. Define GUID Helper (Single Source of Truth) ---
class GUID(TypeDecorator):
    """Platform-independent GUID type."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID

            return dialect.type_descriptor(UUID())
        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return f"{uuid.UUID(value).int:032x}"
            else:
                return f"{value.int:032x}"

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            return value


# --- 2. Define Base (Must be here!) ---
Base = declarative_base()

# --- 3. Engine Configuration ---
is_sqlite = settings.DATABASE_URL.startswith("sqlite")
connect_args = {"uri": True, "check_same_thread": False} if is_sqlite else {}

engine_kwargs = {
    "pool_pre_ping": True,
    "pool_recycle": 1800,
}

if is_sqlite and ":memory:" in settings.DATABASE_URL:
    from sqlalchemy.pool import StaticPool

    engine_kwargs["poolclass"] = StaticPool

sync_database_url = settings.DATABASE_URL.replace("sqlite+aiosqlite", "sqlite")
if ":memory:" in sync_database_url and "cache=shared" not in sync_database_url:
    sync_database_url = (
        sync_database_url + ("&" if "?" in sync_database_url else "?") + "cache=shared"
    )

logger = logging.getLogger("LeadFlowSystem")


@retry(
    stop=stop_after_attempt(5),
    wait=wait_fixed(2),
    before=before_log(logger, logging.WARNING),
    retry=retry_if_exception_type((sqlalchemy.exc.OperationalError, ConnectionRefusedError)),
    reraise=True,
)
async def verify_db_connection() -> None:
    """Verify database connectivity on startup with tenacity retry mechanism."""
    async with async_engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("✅ Database connection verified successfully.")

engine = create_engine(sync_database_url, connect_args=connect_args, **engine_kwargs)

if is_sqlite:

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        # TIER 3 OPTIMIZATION: Write-Ahead Logging (WAL) for high concurrency
        # This prevents "database is locked" errors when multiple leads message at once.
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")  # Wait up to 5s if DB is locked
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

async_database_url = make_url(settings.DATABASE_URL)
if async_database_url.drivername in {"sqlite", "sqlite+pysqlite", "sqlite+aiosqlite"}:
    async_database_url = async_database_url.set(drivername="sqlite+aiosqlite")
    url_str = str(async_database_url)
    if ":memory:" in url_str and "cache=shared" not in url_str:
        async_database_url = make_url(url_str + ("&" if "?" in url_str else "?") + "cache=shared")
elif async_database_url.drivername in {
    "postgres",
    "postgresql",
    "postgresql+psycopg2",
}:
    async_database_url = async_database_url.set(drivername="postgresql+asyncpg")
else:
    raise ValueError(f"Unsupported async database driver: {async_database_url.drivername}")

async_engine_kwargs = {"pool_pre_ping": True, "pool_recycle": 1800}
if async_database_url.drivername.startswith("sqlite"):
    async_engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    async_engine_kwargs.update({"pool_size": 20, "max_overflow": 10, "pool_timeout": 30})

async_engine = create_async_engine(async_database_url, **async_engine_kwargs)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- 4. Tenant Mixin (Uses local GUID) ---
class TenantAwareMixin:
    @declared_attr
    def tenant_id(cls):
        return Column(GUID(), ForeignKey("tenants.id"), nullable=False, index=True)
