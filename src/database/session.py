# Professional English Comment:
# Database engine and session factory configuration.
# Provides a generator for request-scoped database sessions.

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config import settings

# Initialize the SQLAlchemy engine
# Professional English Comment: 
# The DATABASE_URL is fetched from the central settings object.
engine = create_engine(settings.DATABASE_URL)

# Create a session factory for generating database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    Dependency generator for database sessions.
    Ensures that the session is closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()