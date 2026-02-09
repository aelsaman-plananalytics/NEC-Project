"""
Generate Report Router.

Accepts only validation JSON (from /api/validate_programme endpoint).
Produces reports in PDF, DOCX, or HTML format.
Exposes build_validation_report for frontend preview (same structure as PDF).
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Query, Body
from fastapi.responses import Response

from app.reporting.report_generator import ReportGenerator
from app.reporting.validation_report_builder import build_validation_report

router = APIRouter(
    prefix="/api",
    tags=["reporting"],
)


@router.post("/build_validation_report")
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


@router.post("/generate_report")
async def generate_report(
    json_file: UploadFile = File(..., description="Validation JSON file from /api/validate_programme"),
    format: str = Query("pdf", description="Output format: pdf, docx, or html")
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
        
        # Generate report
        generator = ReportGenerator()
        
        # Save to reports folder
        reports_dir = Path(__file__).parent.parent / "outputs" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == "pdf":
            output_path = reports_dir / f"report_{timestamp}.pdf"
            result = generator.generate_pdf(validation_data, output_path=str(output_path))
            media_type = "application/pdf"
            filename = f"nec_validation_report_{timestamp}.pdf"
            # Read the saved file for response
            if isinstance(result, str):
                # File was saved, read it
                with open(result, 'rb') as f:
                    report_bytes = f.read()
            else:
                # Bytes returned, save to file
                with open(output_path, 'wb') as f:
                    f.write(result)
                report_bytes = result
            print(f"[GENERATE_REPORT] Report saved to: {output_path}")
        elif format == "docx":
            output_path = reports_dir / f"report_{timestamp}.docx"
            result = generator.generate_docx(validation_data, output_path=str(output_path))
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            filename = f"nec_validation_report_{timestamp}.docx"
            # Read the saved file for response
            if isinstance(result, str):
                # File was saved, read it
                with open(result, 'rb') as f:
                    report_bytes = f.read()
            else:
                # Bytes returned, save to file
                with open(output_path, 'wb') as f:
                    f.write(result)
                report_bytes = result
            print(f"[GENERATE_REPORT] Report saved to: {output_path}")
        else:  # html
            output_path = reports_dir / f"report_{timestamp}.html"
            report_html = generator.generate_html(validation_data)
            media_type = "text/html"
            filename = f"nec_validation_report_{timestamp}.html"
            # Save HTML to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report_html)
            print(f"[GENERATE_REPORT] Report saved to: {output_path}")
            report_bytes = report_html.encode('utf-8')
        
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
