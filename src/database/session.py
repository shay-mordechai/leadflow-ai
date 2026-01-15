# src/database/session.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config import settings

# Optimized Engine Configuration for Scalability.
# pool_size=20: Keeps 20 connections open to avoid handshake overhead.
# max_overflow=10: Allows 10 temporary connections during spikes.
# pool_pre_ping=True: Checks connection health before use (Prevents "Closed Connection" errors).
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_pre_ping=True,
    pool_recycle=1800  # Recycle connections every 30 mins
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    Dependency generator for database sessions.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
