"""
Version model for NEC Engineering Analysis System.

Represents a version snapshot of project mappings and match results.
"""

from sqlalchemy import Column, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base


class Version(Base):
    """
    Version model representing a snapshot of project mappings.
    
    Versions store the complete mapping JSON for a project at a specific point
    in time, enabling version history and rollback capabilities for the
    NEC compliance report generation.
    """
    
    __tablename__ = "versions"
    
    # Primary key
    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        nullable=False,
        comment="Unique version identifier (UUID as string)"
    )
    
    # Foreign key to project
    project_id = Column(
        String,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the parent project"
    )
    
    # Version data
    mapping_json = Column(
        JSON,
        nullable=False,
        comment="Complete mapping JSON snapshot including all match results"
    )
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Version creation timestamp"
    )
    
    # Relationships
    project = relationship(
        "Project",
        back_populates="versions"
    )
    
    def __repr__(self) -> str:
        """String representation of the version."""
        return f"<Version(id={self.id}, project_id={self.project_id}, created_at={self.created_at})>"



