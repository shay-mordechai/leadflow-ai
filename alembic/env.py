from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import os
import sys

# 1. Add the parent directory to path so we can import src
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# 2. Import settings and models
# We assume Base is in src.database and settings in src.config
try:
    from src.config import settings
    from src.database import Base
    
    # Important: Import models so Base registers them before migration
    # Verify these are the actual class names in your src/models.py
    from src.models import User, Lead, Subscription 
except ImportError as e:
    print(f"Could not import app modules: {e}")
    # If error, try continuing without models (just to check connection)
    Base = None

config = context.config

# 3. Logging configuration
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 4. Connect app models to Alembic
target_metadata = Base.metadata if Base else None

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = str(settings.DATABASE_URL)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    
    # Override the URL in the ini file with the real URL from the code
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = str(settings.DATABASE_URL)
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
