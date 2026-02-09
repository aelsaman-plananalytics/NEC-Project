"""Pydantic schemas for analysis runs (list, create, get)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RunCreate(BaseModel):
    """Payload to save a new analysis run."""

    contract_name: str = Field(..., min_length=1, max_length=512)
    programme_name: str | None = None
    contract_analysis: dict[str, Any] | None = None
    validation_result: dict[str, Any] | None = None


class RunListItem(BaseModel):
    """One run in the list (dashboard)."""

    id: int
    created_at: datetime
    contract_name: str
    programme_name: str | None

    class Config:
        from_attributes = True


class RunDetail(BaseModel):
    """Full run for view / re-download report."""

    id: int
    created_at: datetime
    updated_at: datetime
    contract_name: str
    programme_name: str | None
    contract_analysis: dict[str, Any] | None
    validation_result: dict[str, Any] | None

    class Config:
        from_attributes = True
