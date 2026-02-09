"""
Full-review API: single operation — upload contract + programme, receive validation report PDF.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import Response

from app.orchestration import run_full_review

router = APIRouter(
    prefix="/api",
    tags=["full-review"],
)


@router.post("/full_review")
async def full_review(
    contract_file: UploadFile = File(..., description="NEC contract (PDF)"),
    programme_file: UploadFile = File(..., description="Primavera P6 programme (XER)"),
) -> Response:
    """
    Run full NEC review: analyze contract, validate programme, generate PDF report.

    Upload a contract (PDF) and a programme (XER). Returns only the validation report PDF.
    No intermediate JSON or steps are exposed. Errors are returned in plain language.
    """
    if not contract_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contract file is required.",
        )
    ext = contract_file.filename.lower().rsplit(".", 1)[-1] if "." in contract_file.filename else ""
    if ext not in ("pdf", "docx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contract file must be a PDF or DOCX file.",
        )

    if not programme_file.filename or not programme_file.filename.lower().endswith(".xer"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Programme file must be an XER file.",
        )

    try:
        contract_content = await contract_file.read()
        programme_content = await programme_file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read uploaded files.",
        ) from e

    try:
        pdf_bytes, status_message = run_full_review(
            contract_content,
            contract_file.filename,
            programme_content,
            programme_file.filename,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=validation_report.pdf",
            "X-Status-Message": status_message,
        },
    )
