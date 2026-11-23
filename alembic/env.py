# alembic/env.py
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# 1. Ensure the project root is on sys.path so src modules can be imported
PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 2. Import settings and ALL models so they are registered with Base.metadata
import src.database.models  # noqa: F401
from src.config import settings
from src.database.session import Base

config = context.config

# 3. Configure Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 4. Target metadata for autogenerate support
target_metadata = Base.metadata


def _get_sync_database_url() -> str:
    """
    Resolve the database URL for Alembic migrations and ensure a synchronous driver.
    Prefers dedicated migration URLs (e.g., leadflow_migrator) over runtime DATABASE_URL.
    """
    raw_url = (
        os.getenv("ALEMBIC_DATABASE_URL")
        or os.getenv("MIGRATION_DATABASE_URL")
        or str(settings.DATABASE_URL)
    ).strip()

    if raw_url.startswith("postgresql+asyncpg://"):
        return raw_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+psycopg2://", 1)
    if raw_url.startswith("sqlite+aiosqlite://"):
        return raw_url.replace("sqlite+aiosqlite://", "sqlite://", 1)

    return raw_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode without a live DB connection."""
    url = _get_sync_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_as_batch=url.startswith("sqlite:"),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using a synchronous SQLAlchemy engine."""
    configuration = dict(config.get_section(config.config_ini_section) or {})
    configuration["sqlalchemy.url"] = _get_sync_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            # Enable batch mode only for SQLite ALTER TABLE compatibility
            render_as_batch=connection.dialect.name == "sqlite",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
