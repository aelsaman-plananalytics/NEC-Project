"""
FastAPI dependencies for NEC Engineering Analysis System.

This module provides reusable dependency functions for route handlers,
including database sessions and application settings.
"""

from typing import Generator
from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings, Settings


def db_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database session.
    
    Provides a database session to route handlers. The session is
    automatically closed after the request completes.
    
    Yields:
        Session: SQLAlchemy database session
        
    Example:
        ```python
        @app.get("/projects")
        def get_projects(db: Session = Depends(db_session)):
            # Use db session here
            pass
        ```
    """
    yield from get_db()


def get_settings() -> Settings:
    """
    FastAPI dependency for application settings.
    
    Provides access to the global settings object in route handlers.
    
    Returns:
        Settings: Application settings instance
        
    Example:
        ```python
        @app.get("/config")
        def get_config(settings: Settings = Depends(get_settings)):
            return {"debug": settings.DEBUG}
        ```
    """
    return settings

