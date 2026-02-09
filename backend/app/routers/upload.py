"""
File upload router for NEC Engineering Analysis System.

Handles PDF and XER file uploads for processing.
"""

import os
import tempfile
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, status, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import db_session
from app.models import Project
from app.schemas.project import PDFUploadResponse
from app.services.parsing.parsers.pdf_parser import DocumentParser

# Setup templates for this router
templates_path = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_path))

router = APIRouter(
    prefix="/upload",
    tags=["upload"],
    responses={404: {"description": "Not found"}},
)


@router.get("/pdf", response_class=HTMLResponse)
async def upload_pdf_form(request: Request):
    """
    Display PDF upload form.
    
    Args:
        request: FastAPI request object
        
    Returns:
        HTMLResponse: Rendered upload form template
    """
    return templates.TemplateResponse("upload_pdf.html", {"request": request})


@router.get("/xer", response_class=HTMLResponse)
async def upload_xer_form(request: Request):
    """
    Display XER upload form.
    
    Args:
        request: FastAPI request object
        
    Returns:
        HTMLResponse: Rendered upload form template
    """
    return templates.TemplateResponse("upload_xer.html", {"request": request})


@router.post(
    "/pdf",
    response_model=PDFUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and extract text from NEC contract document",
    description="""
    Uploads a document file (PDF or Word) containing an NEC contract scope document.
    
    The endpoint:
    - Accepts PDF (.pdf) or Word (.docx) file uploads
    - Extracts and normalizes text from the document
    - Creates a new Project record
    - Returns project ID and extraction statistics
    
    The extracted text is cleaned and normalized, ready for chunking in the next phase.
    """,
)
async def upload_pdf(
    request: Request,
    file: UploadFile = File(..., description="NEC contract document (PDF or Word)"),
    project_name: Optional[str] = Form(None),
    db: Session = Depends(db_session),
):
    """
    Upload a document file (PDF or Word) and extract clean text.
    
    Args:
        file: The uploaded document file (PDF or .docx)
        project_name: Optional project name (defaults to filename)
        db: Database session
        
    Returns:
        PDFUploadResponse: Project ID, text length, and success message
        
    Raises:
        HTTPException: If file upload or processing fails
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided"
        )
    
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ['.pdf', '.docx', '.doc']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a PDF (.pdf) or Word document (.docx). Unsupported format."
        )
    
    # Use temporary file for processing
    temp_file_path: Optional[str] = None
    
    try:
        # Create temporary file with appropriate extension
        suffix = file_ext  # Use the detected file extension
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file_path = temp_file.name
            
            # Read uploaded file content
            content = await file.read()
            
            # Validate file is not empty
            if len(content) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Uploaded file is empty"
                )
            
            # Write to temporary file
            temp_file.write(content)
            temp_file.flush()
        
        # Extract text from document (PDF or Word)
        try:
            extracted_text = DocumentParser.extract_text(temp_file_path)
        except FileNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"File processing error: {str(e)}"
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document processing error: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error processing document: {str(e)}"
            )
        
        # Validate extracted text
        if not extracted_text or len(extracted_text.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No text could be extracted from {file_ext.upper()} file. The file may be image-based, corrupted, or contain no readable text."
            )
        
        # Create project record
        project_name = project_name or Path(file.filename).stem
        project = Project(
            name=project_name,
            status="uploaded"
        )
        
        db.add(project)
        db.commit()
        db.refresh(project)
        
        # Note: The extracted text will be processed into ScopeItems in Phase 1.2
        # For now, we return the project_id and text statistics
        text_length = len(extracted_text)
        
        # Check if this is an HTML form submission (browser) or API call
        content_type = request.headers.get("content-type", "")
        is_html_form = "multipart/form-data" in content_type and "application/json" not in content_type
        
        if is_html_form:
            # Return HTML response with success message
            file_type = "PDF" if file_ext == '.pdf' else "Word document"
            return templates.TemplateResponse(
                "upload_pdf.html",
                {
                    "request": request,
                    "message": f"{file_type} uploaded successfully! Project ID: {project.id}, Extracted {text_length:,} characters.",
                    "message_type": "success"
                }
            )
        else:
            # Return JSON response for API calls
            return PDFUploadResponse(
                project_id=project.id,
                text_length=text_length,
                message=f"PDF uploaded and text extracted successfully. Extracted {text_length:,} characters."
            )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during file upload: {str(e)}"
        )
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                # Log error but don't fail the request
                print(f"Warning: Could not delete temporary file {temp_file_path}: {e}")


@router.post("/xer")
async def upload_xer(
    request: Request,
    file: UploadFile = File(..., description="Primavera P6 XER file"),
    project_name: Optional[str] = Form(None),
    db: Session = Depends(db_session),
):
    """
    Upload an XER file (placeholder - to be implemented in future phase).
    
    Args:
        request: FastAPI request object
        file: The uploaded XER file
        project_name: Optional project name
        db: Database session
        
    Returns:
        HTML or JSON response indicating the feature is not yet implemented
    """
    # Check if this is an HTML form submission
    content_type = request.headers.get("content-type", "")
    is_html_form = "multipart/form-data" in content_type and "application/json" not in content_type
    
    message = "XER file upload is not yet implemented. This feature will be available in a future phase."
    
    if is_html_form:
        return templates.TemplateResponse(
            "upload_xer.html",
            {
                "request": request,
                "message": message,
                "message_type": "info"
            }
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=message
        )

