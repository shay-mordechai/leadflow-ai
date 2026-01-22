# src/database/session.py

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from src.config import settings

# Determine if we are using SQLite to apply specific configurations
is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# --- Engine Configuration ---
# For PostgreSQL: We use pooling for performance.
# For SQLite: Pooling is handled differently, and we must ensure thread safety.
connect_args = {"check_same_thread": False} if is_sqlite else {}

engine_kwargs = {
    "pool_pre_ping": True,
    "pool_recycle": 1800,
}

if not is_sqlite:
    # High-concurrency settings for PostgreSQL/MySQL
    engine_kwargs.update({
        "pool_size": 20,
        "max_overflow": 10,
        "pool_timeout": 30,
    })

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    **engine_kwargs
)

# --- SQLite Specific Fixes ---
# Ensure Foreign Keys are enforced in SQLite (disabled by default)
if is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    Dependency generator for database sessions.
    Ensures that every request gets its own session and closes it after completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Tenant Isolation Logic ---

from sqlalchemy import Column, ForeignKey
from sqlalchemy.orm import declared_attr, Session
# Use the same GUID helper we used in models.py for consistency
from src.database.models import GUID

class TenantAwareMixin:
    """
    Mixin to ensure data isolation. Every record is linked to a specific tenant.
    This architecture prevents cross-tenant data leakage.
    """

    @declared_attr
    def tenant_id(cls):
        """
        Foreign Key to the tenants table. 
        Uses custom GUID type for cross-database compatibility (SQLite/Postgres).
        """
        return Column(GUID(), ForeignKey("tenants.id"), nullable=False, index=True)

    @classmethod
    def get_query(cls, session: Session):
        """
        Professional Logic:
        Automatically filters queries by the current tenant ID extracted from the 
        security context. Uses deferred import to prevent circular dependency issues.
        """
        from src.security.tenant import get_tenant_id
        
        current_tenant = get_tenant_id()
        return session.query(cls).filter(cls.tenant_id == current_tenant)