# src/database/session.py
import uuid
from sqlalchemy import create_engine, event, Column, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, declared_attr, Session
from sqlalchemy.types import TypeDecorator, CHAR
from src.config import settings

# --- 1. Define GUID Type Locally (Breaks Circular Dependency) ---
class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise uses CHAR(32), storing as stringified hex values.
    """
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
                return "%.32x" % uuid.UUID(value).int
            else:
                return "%.32x" % value.int

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            return value

# --- 2. Define Base ---
Base = declarative_base()

# --- 3. Engine Configuration ---
is_sqlite = settings.DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

engine_kwargs = {
    "pool_pre_ping": True,
    "pool_recycle": 1800,
}

if not is_sqlite:
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

if is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 4. Tenant Logic (Uses local GUID and Base) ---
class TenantAwareMixin:
    @declared_attr
    def tenant_id(cls):
        return Column(GUID(), ForeignKey("tenants.id"), nullable=False, index=True)

    @classmethod
    def get_query(cls, session: Session):
        from src.security.tenant import get_tenant_id
        current_tenant = get_tenant_id()
        return session.query(cls).filter(cls.tenant_id == current_tenant)