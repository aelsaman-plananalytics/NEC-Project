"""
Pydantic schemas for report generation endpoints.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field


class ReportInput(BaseModel):
    """Schema for report generation input (JSON from analyze_contract)."""

    model_config = ConfigDict(extra="allow")  # Allow additional fields for flexibility

    project: str = Field(..., description="Project name")
    scope_items: List[Dict[str, Any]] = Field(default_factory=list, description="Scope items")
    constraints: List[Dict[str, Any]] = Field(default_factory=list, description="Constraints")
    milestones: List[Dict[str, Any]] = Field(default_factory=list, description="Milestones")
    contract_dates: Dict[str, Any] = Field(default_factory=dict, description="Contract dates")
    starting_date: Optional[str] = Field(None, description="Starting date")
    possession_dates: List[str] = Field(default_factory=list, description="Possession dates")
    completion_date: Optional[str] = Field(None, description="Completion date")
    programme_requirements: Dict[str, Any] = Field(default_factory=dict, description="Programme requirements")
    delay_damages: Optional[str] = Field(None, description="Delay damages")
    defects: Dict[str, Any] = Field(default_factory=dict, description="Defects information")
    payment_terms: Dict[str, Any] = Field(default_factory=dict, description="Payment terms")
    weather_data: Dict[str, Any] = Field(default_factory=dict, description="Weather data")
    extracted_clauses: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Extracted clauses")
    contract_completeness: Dict[str, Any] = Field(default_factory=dict, description="Contract completeness")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Analysis metadata")


class ReportResponse(BaseModel):
    """Schema for report generation response."""
    
    report: str = Field(..., description="Generated narrative report text")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Report metadata")
