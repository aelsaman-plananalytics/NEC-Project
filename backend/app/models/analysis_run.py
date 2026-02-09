"""
AnalysisRun model for NEC Engineering Analysis System.
Stores each user's analysis runs (contract + validation) in the database.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship

from app.database import Base


class AnalysisRun(Base):
    """
    One analysis run belonging to a user: contract analysis + optional programme validation.
    Used for dashboard history, re-download report, and resume/view.
    """

    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    contract_name = Column(String(512), nullable=False, default="")
    programme_name = Column(String(512), nullable=True)

    # Full payloads for re-download report and view; can be large
    contract_analysis = Column(JSON, nullable=True)
    validation_result = Column(JSON, nullable=True)

    user = relationship("User", backref="analysis_runs")
