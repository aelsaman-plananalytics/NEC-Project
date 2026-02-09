"""
Report Request Model.

Schema for report generation requests.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ReportRequest(BaseModel):
    """Report generation request schema."""
    
    extraction_data: Dict[str, Any] = Field(..., description="Contract extraction JSON data")
    programme_data: Optional[Dict[str, Any]] = Field(None, description="Optional P6 programme data")
    format: str = Field("pdf", description="Output format: pdf, docx, or html")
    
    class Config:
        json_schema_extra = {
            "example": {
                "extraction_data": {
                    "project": "Example Project",
                    "extracted_clauses": {}
                },
                "programme_data": None,
                "format": "pdf"
            }
        }
