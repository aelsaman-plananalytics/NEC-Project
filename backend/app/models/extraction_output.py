"""
Extraction Output Model.

Unified schema for contract extraction output.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ExtractionOutput(BaseModel):
    """Unified extraction output schema."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "contract": {
                    "project": "Example Project",
                    "document_type": "complete"
                },
                "clauses": {
                    "3.1": {
                        "title": "Starting Date",
                        "value": "2024-01-01",
                        "status": "filled"
                    }
                },
                "completeness": {
                    "filled_percentage": 85.0,
                    "mandatory_missing": 2
                },
                "metadata": {
                    "filename": "contract.pdf",
                    "total_pages": 50
                }
            }
        }
    )

    contract: Dict[str, Any] = Field(default_factory=dict, description="Contract metadata")
    clauses: Dict[str, Any] = Field(default_factory=dict, description="Extracted clauses")
    completeness: Dict[str, Any] = Field(default_factory=dict, description="Completeness assessment")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Extraction metadata")
