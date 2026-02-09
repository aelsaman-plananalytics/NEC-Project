"""
Full-review orchestration: contract analysis → programme validation → PDF report.

Single entry point: run_full_review(contract_content, contract_filename, programme_content, programme_filename).
Intermediate JSON is not persisted or exposed. Deterministic, repeatable, production-ready.
"""

import tempfile
import os
from pathlib import Path
from typing import Tuple

from app.routers.analyze_contract import _run_contract_analysis_from_path
from app.routers.validate_programme import _run_programme_validation
from app.reporting.report_generator import ReportGenerator


def run_full_review(
    contract_content: bytes,
    contract_filename: str,
    programme_content: bytes,
    programme_filename: str,
) -> Tuple[bytes, str]:
    """
    Run the full NEC review pipeline: analyze contract → validate programme → generate PDF.

    - contract_content: PDF file bytes
    - contract_filename: original filename (e.g. "contract.pdf") for metadata
    - programme_content: XER file bytes
    - programme_filename: original filename (e.g. "programme.xer") for metadata

    Returns (pdf_bytes, status_message). Intermediate JSON is not saved or exposed.
    Fails fast with plain-language errors if any step fails.
    """
    temp_contract_path = None
    try:
        # 1. Contract analysis (internal)
        file_ext = Path(contract_filename).suffix.lower()
        if file_ext not in (".pdf", ".docx"):
            raise ValueError("Contract file must be a PDF or DOCX file.")
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            tmp.write(contract_content)
            temp_contract_path = tmp.name

        print("[FULL_REVIEW] Running contract analysis...")
        analysis_json = _run_contract_analysis_from_path(
            temp_contract_path, contract_filename, contract_content
        )
        print("[FULL_REVIEW] Contract analysis complete.")

        # 2. Programme validation (internal)
        if not programme_filename.lower().endswith(".xer"):
            raise ValueError("Programme file must be an XER file.")
        print("[FULL_REVIEW] Running programme validation...")
        validation_json = _run_programme_validation(
            analysis_json,
            programme_content,
            programme_filename,
            contract_filename,
        )
        print("[FULL_REVIEW] Programme validation complete.")

        # 3. Report generation (user-facing output)
        print("[FULL_REVIEW] Generating PDF report...")
        generator = ReportGenerator()
        pdf_bytes = generator.generate_pdf(validation_json)
        if isinstance(pdf_bytes, str):
            with open(pdf_bytes, "rb") as f:
                pdf_bytes = f.read()

        # 4. Status message from validation summary
        vs = validation_json.get("validation_summary", {})
        acceptability = vs.get("acceptability_status", "")
        overall = vs.get("overall_status", "")
        if acceptability == "ACCEPTABLE":
            status_message = "Programme acceptable under NEC."
        elif overall == "pass":
            status_message = "Programme passes validation."
        elif overall == "fail":
            status_message = "Programme does not meet NEC requirements."
        else:
            status_message = "Review complete. See report for details."

        print("[FULL_REVIEW] Pipeline complete.")
        return (pdf_bytes, status_message)

    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        # Plain-language message; log details internally only
        print(f"[FULL_REVIEW] Error: {e}")
        if "contract" in str(e).lower() or "analysis" in str(e).lower():
            raise RuntimeError("Contract analysis failed. Please check that the file is a valid NEC contract PDF.") from e
        if "programme" in str(e).lower() or "xer" in str(e).lower() or "validation" in str(e).lower():
            raise RuntimeError("Programme validation failed. Please check that the file is a valid Primavera P6 XER file.") from e
        if "report" in str(e).lower() or "pdf" in str(e).lower():
            raise RuntimeError("Report generation failed. Please try again.") from e
        raise RuntimeError("Review failed. Please check your contract and programme files and try again.") from e
    finally:
        if temp_contract_path and os.path.exists(temp_contract_path):
            try:
                os.unlink(temp_contract_path)
            except Exception:
                pass
