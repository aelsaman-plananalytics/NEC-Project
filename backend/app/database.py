"""
Database configuration and session management for NEC Engineering Analysis System.

This module sets up SQLAlchemy ORM with database connection, session management,
and provides a dependency function for FastAPI route handlers.
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings

# Create database engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG,  # Log SQL queries in debug mode
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Base class for declarative models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency generator.
    
    Yields a database session and ensures it's properly closed after use.
    This function is designed to be used as a FastAPI dependency.
    
    Yields:
        Session: SQLAlchemy database session
        
    Example:
        ```python
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            # Use db session here
            pass
        ```
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

