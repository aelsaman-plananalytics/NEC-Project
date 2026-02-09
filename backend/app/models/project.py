"""
Project model for NEC Engineering Analysis System.

Represents a project that contains scope items, activities, match results, and versions.
"""

from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base


class Project(Base):
    """
    Project model representing an NEC contract analysis project.
    
    A project tracks the analysis of a single NEC contract (scope PDF) against
    a Primavera P6 programme (XER file). It contains scope items, activities,
    match results, and version history.
    """
    
    __tablename__ = "projects"
    
    # Primary key
    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        nullable=False,
        comment="Unique project identifier (UUID as string)"
    )
    
    # Project metadata
    name = Column(
        String(255),
        nullable=False,
        comment="Project name/identifier"
    )
    
    status = Column(
        String(50),
        nullable=False,
        default="uploaded",
        comment="Project status: uploaded, processing, or completed"
    )
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Project creation timestamp"
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
        comment="Last update timestamp"
    )
    
    # Relationships
    scope_items = relationship(
        "ScopeItem",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    
    activities = relationship(
        "ActivityItem",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    
    match_results = relationship(
        "MatchResult",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    
    versions = relationship(
        "Version",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    
    def __repr__(self) -> str:
        """String representation of the project."""
        return f"<Project(id={self.id}, name='{self.name}', status='{self.status}')>"

