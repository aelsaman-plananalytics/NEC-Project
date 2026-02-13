"""
Pydantic schemas for Project-related API requests and responses.
"""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    """Schema for creating a new project."""

    name: str = Field(..., description="Project name/identifier", max_length=255)


class ProjectResponse(BaseModel):
    """Schema for project response."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Project ID (UUID)")
    name: str = Field(..., description="Project name")
    status: str = Field(..., description="Project status")
    created_at: Optional[str] = Field(None, description="Creation timestamp")


class PDFUploadResponse(BaseModel):
    """Schema for PDF upload response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "project_id": "123e4567-e89b-12d3-a456-426614174000",
                "text_length": 45230,
                "message": "PDF uploaded and text extracted successfully"
            }
        }
    )

    project_id: str = Field(..., description="Created project ID (UUID)")
    text_length: int = Field(..., description="Length of extracted text in characters")
    message: str = Field(..., description="Success message")



