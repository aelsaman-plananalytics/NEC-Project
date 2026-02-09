"""
Activity item model for NEC Engineering Analysis System.

Represents an activity extracted from a Primavera P6 XER file.
"""

from sqlalchemy import Column, String, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base


class ActivityItem(Base):
    """
    Activity item model representing a task or activity from a Primavera P6 programme.
    
    Activities are extracted from the XER file and contain activity codes,
    descriptions, WBS information, raw text, cleaned text, extracted features,
    and optional embedding vectors for semantic matching against scope items.
    """
    
    __tablename__ = "activities"
    
    # Primary key
    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        nullable=False,
        comment="Unique activity identifier (UUID as string)"
    )
    
    # Foreign key to project
    project_id = Column(
        String,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the parent project"
    )
    
    # Activity data
    activity_code = Column(
        String(100),
        nullable=True,
        comment="Activity code from Primavera P6"
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Activity description from Primavera P6"
    )
    
    wbs = Column(
        String(255),
        nullable=True,
        comment="Work Breakdown Structure (WBS) code"
    )
    
    raw_text = Column(
        Text,
        nullable=False,
        comment="Original raw text extracted from the XER file"
    )
    
    clean_text = Column(
        Text,
        nullable=True,
        comment="Cleaned and normalized text after preprocessing"
    )
    
    features = Column(
        JSON,
        nullable=True,
        comment="Extracted features (keywords, entities, etc.) as JSON"
    )
    
    embedding_id = Column(
        String(255),
        nullable=True,
        comment="Reference ID for the vector embedding in the vector database"
    )
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Activity creation timestamp"
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
        comment="Last update timestamp"
    )
    
    # Relationships
    project = relationship(
        "Project",
        back_populates="activities"
    )
    
    match_results = relationship(
        "MatchResult",
        back_populates="activity_item",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    
    def __repr__(self) -> str:
        """String representation of the activity item."""
        return f"<ActivityItem(id={self.id}, code='{self.activity_code}', project_id={self.project_id})>"

