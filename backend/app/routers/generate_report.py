"""
Generate Report Router.

Accepts only validation JSON (from /api/validate_programme endpoint).
Produces reports in PDF, DOCX, or HTML format.
Exposes build_validation_report for frontend preview (same structure as PDF).
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Query, Body, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.reporting.report_generator import ReportGenerator
from app.reporting.validation_report_builder import build_validation_report
from app.runtime_paths import RUNTIME_DIR
from app.database import get_db
from app.storage import get_storage
from app.models.analysis_run import AnalysisRun
from app.routers.auth import get_current_user_optional
from app.models.user import User

router = APIRouter(
    prefix="/api",
    tags=["reporting"],
)


# Deprecated: use POST /api/v1/build_validation_report. Kept for backward compatibility.
@router.post("/build_validation_report", deprecated=True, include_in_schema=False)
@router.post("/v1/build_validation_report")
async def build_validation_report_endpoint(
    body: Dict[str, Any] = Body(..., description="Validation JSON from /api/validate_programme"),
) -> Dict[str, Any]:
    """
    Build the same structured report data used for the PDF.
    Returns section_a (executive summary), section_d (required activities), scope/constraint alignment, next steps, etc.
    Use this for the web Validation Review preview so it matches the downloaded report.
    """
    required = ["contract_summary", "programme_summary", "alignment"]
    missing = [f for f in required if f not in body]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid validation JSON. Missing: {', '.join(missing)}.",
        )
    try:
        return build_validation_report(body)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not build report: {str(e)}",
        )


# Deprecated: use POST /api/v1/generate_report. Kept for backward compatibility.
@router.post("/generate_report", deprecated=True, include_in_schema=False)
@router.post("/v1/generate_report")
async def generate_report(
    json_file: UploadFile = File(..., description="Validation JSON file from /api/validate_programme"),
    format: str = Query("pdf", description="Output format: pdf, docx, or html"),
    confidentiality_mode: Optional[str] = Form(None, description="If 'true', redact activity names in report"),
    organisation_logo_url: Optional[str] = Form(None, description="URL for organisation logo (header/footer)"),
    user_name: Optional[str] = Form(None, description="User name for report header/footer"),
    run_id: Optional[int] = Form(None, description="If set, use this run's preferences_snapshot (requires auth)"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> Response:
    """
    Generate professional report from validation JSON.
    
    Accepts ONLY validation JSON files from /api/validate_programme.
    Does NOT accept contract analysis JSON or PDF/DOCX files.
    
    Args:
        json_file: Validation JSON file from /api/validate_programme (required)
        format: Output format (pdf, docx, or html)
        
    Returns:
        Response with generated report file
    """
    # Validate JSON file
    if json_file.content_type and json_file.content_type not in ["application/json", "text/json"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JSON files are accepted. Must be validation JSON from /api/validate_programme."
        )
    
    if json_file.filename and not json_file.filename.endswith('.json'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must have .json extension."
        )
    
    # Validate format
    if format not in ["pdf", "docx", "html"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format must be 'pdf', 'docx', or 'html'."
        )
    
    try:
        # Load JSON data
        contents = await json_file.read()
        validation_data = json.loads(contents.decode('utf-8'))
        
        # Validate that this is a validation JSON
        required_fields = ["contract_summary", "programme_summary", "alignment"]
        missing_fields = [field for field in required_fields if field not in validation_data]
        
        if missing_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid validation JSON. Missing required fields: {', '.join(missing_fields)}. "
                       f"This endpoint only accepts validation JSON from /api/validate_programme."
            )
        
        print(f"[GENERATE_REPORT] Generating report from validation JSON: {json_file.filename}")
        
        # Report options: from run's preferences_snapshot when run_id provided (historical run), else from form
        report_options = {}
        if run_id is not None:
            if current_user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required when generating report for a saved run (run_id).",
                )
            run = db.query(AnalysisRun).filter(
                AnalysisRun.id == run_id,
                AnalysisRun.user_id == current_user.id,
            ).first()
            if not run:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Analysis run not found.",
                )
            snapshot = getattr(run, "preferences_snapshot", None) or {}
            if isinstance(snapshot, dict):
                report_options = dict(snapshot)
            if current_user and (not report_options.get("user_name")):
                report_options["user_name"] = (current_user.name or "").strip() or None
        else:
            if confidentiality_mode == "true":
                report_options["confidentiality_mode"] = True
            if organisation_logo_url and organisation_logo_url.strip():
                report_options["organisation_logo_url"] = organisation_logo_url.strip()
            if user_name and user_name.strip():
                report_options["user_name"] = user_name.strip()
        if report_options:
            validation_data["_report_options"] = report_options
        
        # Generate report
        from app.performance import log_performance_metric
        import time as _time
        generator = ReportGenerator()
        storage = get_storage()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        _t0 = _time.time()
        if format == "pdf":
            result = generator.generate_pdf(validation_data, output_path=None, report_options=validation_data.get("_report_options"))
            report_bytes = result if isinstance(result, bytes) else (open(result, "rb").read() if isinstance(result, str) else b"")
            storage.save_bytes(f"reports/report_{timestamp}.pdf", report_bytes)
            media_type = "application/pdf"
            filename = f"nec_validation_report_{timestamp}.pdf"
            print(f"[GENERATE_REPORT] Report saved to storage: reports/report_{timestamp}.pdf")
        elif format == "docx":
            result = generator.generate_docx(validation_data, output_path=None, report_options=validation_data.get("_report_options"))
            report_bytes = result if isinstance(result, bytes) else (open(result, "rb").read() if isinstance(result, str) else b"")
            storage.save_bytes(f"reports/report_{timestamp}.docx", report_bytes)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            filename = f"nec_validation_report_{timestamp}.docx"
            print(f"[GENERATE_REPORT] Report saved to storage: reports/report_{timestamp}.docx")
        else:  # html
            report_html = generator.generate_html(validation_data, report_options=validation_data.get("_report_options"))
            report_bytes = report_html.encode("utf-8")
            storage.save_bytes(f"reports/report_{timestamp}.html", report_bytes)
            media_type = "text/html"
            filename = f"nec_validation_report_{timestamp}.html"
            print(f"[GENERATE_REPORT] Report saved to storage: reports/report_{timestamp}.html")
        log_performance_metric("report_generation", (_time.time() - _t0) * 1000)
        return Response(
            content=report_bytes,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON format: {str(e)}"
        )
    except Exception as e:
        import traceback
        print(f"[GENERATE_REPORT] Error: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating report: {str(e)}"
        )
