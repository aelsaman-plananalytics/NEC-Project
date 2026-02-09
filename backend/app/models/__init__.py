"""
Models Module.

Contains both database models (SQLAlchemy ORM) and API models (Pydantic).
"""

# Database models (SQLAlchemy ORM)
from app.models.project import Project
from app.models.scope_item import ScopeItem
from app.models.activity_item import ActivityItem
from app.models.match_result import MatchResult
from app.models.version import Version

# User model may not exist yet
try:
    from app.models.user import User
except ImportError:
    User = None  # User model not implemented yet

# API models (Pydantic)
from app.models.extraction_output import ExtractionOutput
from app.models.programme_output import ProgrammeOutput
from app.models.report_request import ReportRequest

__all__ = [
    # Database models
    "Project",
    "ScopeItem",
    "ActivityItem",
    "MatchResult",
    "Version",
    # API models
    "ExtractionOutput",
    "ProgrammeOutput",
    "ReportRequest",
]

# Conditionally add User if it exists
if User is not None:
    __all__.append("User")
