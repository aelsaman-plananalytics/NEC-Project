"""Pydantic schemas for analysis runs (list, create, get)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RunCreate(BaseModel):
    """Payload to save a new analysis run. preferences_snapshot is built server-side from current user."""

    contract_name: str = Field(..., min_length=1, max_length=512)
    programme_name: str | None = None
    contract_analysis: dict[str, Any] | None = None
    validation_result: dict[str, Any] | None = None
    preferences_snapshot: dict[str, Any] | None = None  # optional; server builds from user if omitted
    status: str | None = None  # optional; default completed


class RunListItem(BaseModel):
    """One run in the list (dashboard). Optional summary fields from validation_result."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    contract_name: str
    programme_name: str | None
    acceptability_status: str | None = None
    submission_stage: str | None = None
    has_comparison: bool = False
    status: str = "completed"  # processing | completed | failed | timed_out


class RunDetail(BaseModel):
    """Full run for view / re-download report."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    contract_name: str
    programme_name: str | None
    contract_analysis: dict[str, Any] | None
    validation_result: dict[str, Any] | None
    preferences_snapshot: dict[str, Any] | None = None
    status: str = "completed"
