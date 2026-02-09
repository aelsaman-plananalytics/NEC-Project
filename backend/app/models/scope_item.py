"""
Scope item model for NEC Engineering Analysis System.

Represents a scope item extracted from an NEC contract PDF document.
"""

from sqlalchemy import Column, String, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base


class ScopeItem(Base):
    """
    Scope item model representing a clause or requirement from an NEC contract.
    
    Scope items are extracted from the contract PDF and contain raw text,
    cleaned text, extracted features, and optional embedding vectors for
    semantic matching against activities.
    """
    
    __tablename__ = "scope_items"
    
    # Primary key
    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        nullable=False,
        comment="Unique scope item identifier (UUID as string)"
    )
    
    # Foreign key to project
    project_id = Column(
        String,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the parent project"
    )
    
    # Scope item data
    section_number = Column(
        String(100),
        nullable=True,
        comment="Section or clause number from the contract"
    )
    
    raw_text = Column(
        Text,
        nullable=False,
        comment="Original raw text extracted from the PDF"
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
        comment="Scope item creation timestamp"
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
        back_populates="scope_items"
    )
    
    match_results = relationship(
        "MatchResult",
        back_populates="scope_item",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    
    def __repr__(self) -> str:
        """String representation of the scope item."""
        return f"<ScopeItem(id={self.id}, section='{self.section_number}', project_id={self.project_id})>"

