"""
User model for NEC Engineering Analysis System.
Stored in PostgreSQL; used for auth and account settings.
"""

from datetime import datetime, date
from sqlalchemy import Column, Integer, String, DateTime, Date, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base

# Default preferences (presentation/workflow only; do not affect validation or acceptability)
DEFAULT_PREFERENCES = {
    "programme_stage_assumption": "auto",
    "reporting_posture": "conservative",
    "show_confidence_indicators": True,
    "expand_assurance_by_default": False,
    "always_show_contract_excerpts": False,
    "always_show_activity_names": True,
    "default_report_format": "pdf",
    "auto_download_report": False,
    "include_user_notes_by_default": True,
    "include_timestamps_authorship": True,
    "confidentiality_mode": False,
}


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False, default="")
    organisation = Column(String(255), nullable=False, default="")
    role = Column(String(64), nullable=False, default="Consultant")  # Client | Contractor | Consultant
    timezone = Column(String(128), nullable=False, default="UTC")
    report_naming_preference = Column(String(64), nullable=False, default="contract_date_validation")
    data_retention_days = Column(Integer, nullable=False, default=365)
    organisation_logo_url = Column(String(512), nullable=True)
    preferences = Column(JSONB, nullable=True)
    # Email verification (SMTP-based)
    is_verified = Column(Boolean, nullable=False, default=False)
    email_verification_token = Column(String(255), nullable=True, index=True)
    email_verification_expires = Column(DateTime, nullable=True)
    # Password reset (SMTP-based)
    password_reset_token = Column(String(255), nullable=True, index=True)
    password_reset_expires = Column(DateTime, nullable=True)
    # Plan gating (no billing yet)
    plan_type = Column(String(64), nullable=False, default="free")
    monthly_run_limit = Column(Integer, nullable=False, default=10)
    runs_this_month = Column(Integer, nullable=False, default=0)
    runs_reset_date = Column(Date, nullable=True)  # when to reset runs_this_month to 0
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
