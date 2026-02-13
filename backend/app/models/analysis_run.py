"""
AnalysisRun model for NEC Engineering Analysis System.
Stores each user's analysis runs (contract + validation) in the database.
Run-level immutability: validation_result must not be modified after insert.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, event
from sqlalchemy.orm import attributes
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

    # Snapshot of user preferences at run creation (confidentiality_mode, default_report_format, etc.)
    preferences_snapshot = Column(JSON, nullable=True)

    # Lifecycle: processing | completed | failed | timed_out
    status = Column(String(32), nullable=False, default="completed", server_default="completed")

    user = relationship("User", backref="analysis_runs")


@event.listens_for(AnalysisRun, "before_update")
def _reject_validation_result_update(mapper, connection, target):
    """Raise RuntimeError if validation_result is modified after insert, except one-time set from None to result."""
    hist = attributes.get_history(target, "validation_result")
    if not hist.has_changes() or not (hist.added or hist.deleted):
        return
    # Allow exactly one transition: None -> dict (router sets validation_result and status together, so status may already be "completed" here)
    if (
        hist.deleted
        and hist.added
        and len(hist.deleted) == 1
        and len(hist.added) == 1
        and hist.deleted[0] is None
        and hist.added[0] is not None
    ):
        return
    raise RuntimeError(
        "AnalysisRun.validation_result is immutable after insert; modification is not allowed."
    )
