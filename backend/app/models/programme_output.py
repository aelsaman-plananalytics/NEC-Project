"""
Programme Output Model.

Schema for comprehensive P6 programme validation output.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class ProgrammeOutput(BaseModel):
    """Comprehensive programme validation output schema."""
    
    contract_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted NEC contract clauses (3.1, 3.2, 3.3, etc.)"
    )
    programme_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted programme data (activities, calendars, critical path, etc.)"
    )
    nec_alignment: Dict[str, Any] = Field(
        default_factory=dict,
        description="NEC-P6 alignment checks (start date, completion, possession, etc.)"
    )
    logic_checks: Dict[str, Any] = Field(
        default_factory=dict,
        description="Programme logic check results (broken logic, negative float, etc.)"
    )
    risks: Dict[str, Any] = Field(
        default_factory=dict,
        description="Risk assessment (critical, major, minor)"
    )
    validation_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Validation summary with scores and overall status"
    )
    schedule_health: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Schedule health index (optional, for backward compatibility)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Validation metadata (timestamp, file paths, etc.)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "contract_summary": {
                    "3.1": {"title": "Starting Date", "value": "2024-01-01", "status": "filled"},
                    "3.3": {"title": "Completion Date", "value": "2025-12-31", "status": "filled"}
                },
                "programme_summary": {
                    "total_activities": 100,
                    "data_date": "2024-01-01",
                    "critical_path": []
                },
                "nec_alignment": {
                    "start_date_alignment": {"status": "match"},
                    "completion_date": {"status": "before"}
                },
                "logic_checks": {
                    "negative_float": {"status": "pass", "count": 0}
                },
                "risks": {
                    "critical": [],
                    "major": [],
                    "minor": []
                },
                "validation_summary": {
                    "nec_alignment_score": 85,
                    "schedule_quality_score": 90,
                    "overall_status": "pass",
                    "issues_found": 2
                }
            }
        }
