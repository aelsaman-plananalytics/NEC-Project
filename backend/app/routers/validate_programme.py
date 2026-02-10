"""
Validate Programme Router.

Validates Primavera P6 programme against NEC contract with comprehensive validation.
Supports both legacy contract JSON (extracted_clauses) and new analyze_contract output
(project, scope_items, programme_compliance_model, contract_dates, etc.).
"""

import json
import tempfile
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Any, Dict
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import JSONResponse

from app.p6_engine.xer_loader import XERLoader
from app.p6_engine.logic_checks import LogicChecker
from app.p6_engine.comprehensive_validator import ComprehensiveValidator
from app.p6_engine.validation_ai_review import review_validation
from app.p6_engine.frozen_requirements import build_frozen_requirements
from app.p6_engine.submission_lifecycle import (
    prepare_contract_for_validation,
    get_stage_expectations,
    compute_obligation_readiness,
    normalize_submission_stage,
)
from app.api_contract import (
    enrich_obligation_readiness_with_report,
    assert_acceptability_authority,
    _normalize_acceptability,
)

router = APIRouter(
    prefix="/api",
    tags=["validation"],
)


def _get_latest_analysis_json_path() -> Optional[Path]:
    """Return path to the latest JSON in outputs/analysis_reports, or None."""
    analysis_dir = Path(__file__).parent.parent / "outputs" / "analysis_reports"
    if not analysis_dir.exists():
        return None
    json_files = list(analysis_dir.glob("analysis_*.json"))
    if not json_files:
        return None
    return max(json_files, key=lambda p: p.stat().st_mtime)


def _run_programme_validation(
    contract_data: dict,
    xer_content: bytes,
    xer_filename: str,
    contract_filename: str = "contract.pdf",
    submission_stage: Optional[str] = None,
    obligation_readiness: Optional[List[Dict[str, Any]]] = None,
) -> dict:
    """
    Run programme validation. Used by the validate_programme endpoint and by the full-review orchestrator.
    Returns the validation dict; does not persist to disk.
    """
    temp_xer_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xer') as tmp:
            tmp.write(xer_content)
            temp_xer_path = tmp.name

        xer_loader = XERLoader()
        p6_data = xer_loader.load_xer(temp_xer_path)

        logic_checker = LogicChecker()
        logic_checks = logic_checker.check_logic(p6_data)

        validator = ComprehensiveValidator()
        validation_output = validator.validate(contract_data, p6_data)

        validation_output["logic_checks"] = logic_checks
        validation_output["schedule_health"] = validator._calculate_schedule_health(
            validation_output["programme_summary"], logic_checks
        )
        # SINGLE AUTHORITY: validation_summary (including acceptability_status / overall_status) is set only inside validator.validate().
        # Do NOT recalculate or overwrite here; when obligation_entities_used, acceptability comes only from _validate_obligation_entities.
        validation_output["alignment"] = validation_output.pop("nec_alignment", {})

        if "circular_dependencies" in logic_checks:
            circular_deps = logic_checks.get("circular_dependencies", {}).get("cycles", [])
            validation_output["programme_summary"]["circular_dependencies"] = circular_deps

        output_dict = {
            "contract_summary": validation_output.get("contract_summary", {}),
            "programme_summary": validation_output.get("programme_summary", {}),
            "alignment": validation_output.get("alignment", {}),
            "nec_alignment_detailed": validation_output.get("nec_alignment_detailed", {}),
            "programme_kpis": validation_output.get("programme_kpis", {}),
            "schedule_health": validation_output.get("schedule_health", {}),
            "logic_checks": logic_checks,
            "risks": validation_output.get("risks", {}),
            "risk_summary": validation_output.get("risks", {}),
            "recommendations": validation_output.get("recommendations", []),
            "validation_summary": validation_output.get("validation_summary", {}),
            "metadata": {
                "validation_timestamp": datetime.now().isoformat(),
                "contract_file": contract_filename,
                "xer_file": xer_filename,
            }
        }
        # Layer 2: planner lifecycle (does not change acceptability_status or overall_status)
        if submission_stage is not None:
            output_dict["submission_stage"] = submission_stage
            output_dict["lifecycle_expectations"] = get_stage_expectations(submission_stage)
        if obligation_readiness is not None:
            output_dict["obligation_readiness"] = obligation_readiness

        try:
            ai_review = review_validation(
                output_dict["contract_summary"],
                output_dict["programme_summary"],
                output_dict["alignment"],
                output_dict["validation_summary"],
            )
            output_dict["ai_review"] = ai_review
        except Exception as ai_err:
            output_dict["ai_review"] = {"skipped": True, "reason": str(ai_err)}

        return output_dict
    finally:
        if temp_xer_path and os.path.exists(temp_xer_path):
            try:
                os.unlink(temp_xer_path)
            except Exception:
                pass


@router.post("/validate_programme")
async def validate_programme(
    xer_file: UploadFile = File(..., description="XER file from Primavera P6"),
    json_file: Optional[UploadFile] = File(None, description="Optional: JSON from /api/analyze_contract; if omitted, latest from outputs/analysis_reports is used"),
    submission_stage_form: Optional[str] = Form(None, description="Optional: submission stage (e.g. first_programme, revised_programme, update) for lifecycle"),
    planner_assumptions_form: Optional[str] = Form(None, description="Optional: JSON array of { obligation_id, assumption_type, rationale } for planner-declared assumptions"),
) -> JSONResponse:
    """
    Validate Primavera P6 programme against NEC contract.
    
    Performs comprehensive validation including:
    - Contract clause extraction
    - Programme data extraction
    - NEC alignment checks (including programme_compliance_model when present)
    - Risk assessment
    - Validation scoring
    
    Args:
        xer_file: Primavera P6 XER file
        json_file: Optional contract analysis JSON from /api/analyze_contract.
                   If omitted, the latest JSON in outputs/analysis_reports is used.
        
    Returns:
        JSONResponse with complete validation results
    """
    if not xer_file.filename or not xer_file.filename.endswith('.xer'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Programme data must be an XER file."
        )

    try:
        # Load contract JSON: from upload or latest in analysis_reports
        if json_file and json_file.filename and json_file.filename.endswith('.json'):
            print(f"[VALIDATE_PROGRAMME] Loading contract JSON from upload: {json_file.filename}")
            json_content = await json_file.read()
            contract_data = json.loads(json_content.decode('utf-8'))
            contract_source = json_file.filename
            n_required = len(contract_data.get("programme_compliance_model", {}).get("required_activities", []) or [])
            print(f"[VALIDATE_PROGRAMME] Contract has {n_required} required_activities in uploaded JSON")
        else:
            latest_path = _get_latest_analysis_json_path()
            if not latest_path:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No contract JSON provided and no analysis report found in outputs/analysis_reports. Upload a JSON file or run /api/analyze_contract first."
                )
            print(f"[VALIDATE_PROGRAMME] Loading latest contract JSON: {latest_path.name}")
            with open(latest_path, 'r', encoding='utf-8') as f:
                contract_data = json.load(f)
            contract_source = latest_path.name
        
        # Accept both formats: legacy (extracted_clauses) or new (contract_dates / programme_compliance_model / project)
        if "extracted_clauses" not in contract_data and "contract_dates" not in contract_data and "programme_compliance_model" not in contract_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid contract JSON: expected 'extracted_clauses' (legacy) or 'contract_dates' / 'programme_compliance_model' (analyze_contract output)."
            )

        # Reject stale obligation_entities so we never trust old artefacts (even before we overwrite them).
        _CURRENT_FROZEN_VERSION = 7
        oe = contract_data.get("obligation_entities") or {}
        if oe and isinstance(oe, dict) and (oe.get("frozen_requirements_version") or 0) < _CURRENT_FROZEN_VERSION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Contract JSON has stale obligation_entities (version {oe.get('frozen_requirements_version', 0)}). Re-run contract analysis to get version {_CURRENT_FROZEN_VERSION} before validating."
            )

        # LIFECYCLE INVARIANT: All obligation entities MUST be rebuilt at validation time using current
        # obligation-construction logic. Validation must NEVER trust obligation_entities stored in
        # the uploaded or latest analysis JSON (they were built at analysis time and can be stale or
        # predate logic changes e.g. mandatory Temporary Works). Rebuilding here ensures mandatory
        # obligations always appear in obligations_report, programmes missing them FAIL acceptability,
        # and scope & constraints sections reflect the same single source of truth.
        try:
            frozen = build_frozen_requirements(contract_data)
            contract_data["obligation_entities"] = frozen["obligation_entities"]
            contract_data["frozen_requirements"] = frozen["frozen_requirements"]
        except Exception as e:
            contract_data["obligation_entities"] = {"obligations": [], "validation_error": str(e)}
            contract_data["frozen_requirements"] = []

        # Layer 2: planner lifecycle — apply stage and merge assumptions (does not change acceptability logic)
        # API contract: accept "initial" | "interim" | "final" (and internal names); echo back for response
        submission_stage_api: Optional[str] = (submission_stage_form.strip() or None) if submission_stage_form else None
        submission_stage_internal = normalize_submission_stage(submission_stage_api) if submission_stage_api else None
        planner_assumptions_used: List[Dict[str, Any]] = []
        if planner_assumptions_form:
            try:
                planner_assumptions_used = json.loads(planner_assumptions_form)
                if not isinstance(planner_assumptions_used, list):
                    planner_assumptions_used = []
            except (json.JSONDecodeError, TypeError):
                planner_assumptions_used = []
        contract_data = prepare_contract_for_validation(contract_data, submission_stage_internal, planner_assumptions_used)
        obligations_for_readiness = (contract_data.get("obligation_entities") or {}).get("obligations") or []
        obligation_readiness = compute_obligation_readiness(obligations_for_readiness, submission_stage_internal) if obligations_for_readiness else []

        print(f"[VALIDATE_PROGRAMME] Loading XER file: {xer_file.filename}")
        xer_content = await xer_file.read()
        output_dict = _run_programme_validation(
            contract_data, xer_content, xer_file.filename, contract_source,
            submission_stage=submission_stage_internal or submission_stage_api,
            obligation_readiness=obligation_readiness,
        )
        if planner_assumptions_used:
            output_dict["planner_assumptions_used"] = planner_assumptions_used

        # API contract: top-level authoritative fields (copy only from validator; never recompute)
        scope_coverage = (output_dict.get("alignment") or {}).get("scope_coverage") or {}
        vs = output_dict.get("validation_summary") or {}
        raw_acceptability = vs.get("acceptability_status")
        output_dict["acceptability_status"] = _normalize_acceptability(raw_acceptability) or raw_acceptability
        output_dict["overall_status"] = vs.get("overall_status")
        output_dict["obligations_report"] = scope_coverage.get("obligations_report", [])
        output_dict["obligations_not_represented_but_mandatory"] = scope_coverage.get("obligations_not_represented_but_mandatory", [])
        output_dict["scope_evidence_table"] = scope_coverage.get("scope_evidence_table", [])
        output_dict["submission_stage"] = submission_stage_api

        # Enrich obligation_readiness (guidance only) with aligned and required_action from validator report
        readiness = output_dict.get("obligation_readiness") or []
        if readiness and scope_coverage.get("obligations_report"):
            output_dict["obligation_readiness"] = enrich_obligation_readiness_with_report(
                readiness, scope_coverage["obligations_report"]
            )

        assert_acceptability_authority(
            output_dict.get("validation_summary") or {},
            output_dict.get("acceptability_status"),
            output_dict.get("overall_status"),
        )

        # Save to validation_reports folder
        validation_dir = Path(__file__).parent.parent / "outputs" / "validation_reports"
        validation_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"validation_{timestamp}.json"
        output_path = validation_dir / output_filename
        
        # Add output path to metadata
        output_dict["metadata"]["output_path"] = str(output_path)
        output_dict["metadata"]["output_filename"] = output_filename
        
        # Save to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_dict, f, indent=2, ensure_ascii=False)
        
        print(f"[VALIDATE_PROGRAMME] Validation results saved to: {output_path}")
        vs = output_dict.get("validation_summary", {})
        print(f"[VALIDATE_PROGRAMME] NEC Alignment Score: {vs.get('nec_alignment_score', 0)}%")
        print(f"[VALIDATE_PROGRAMME] Schedule Quality Score: {vs.get('schedule_quality_score', 0)}%")
        print(f"[VALIDATE_PROGRAMME] Overall Status: {vs.get('overall_status', 'unknown')}")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=output_dict
        )
        
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON format: {str(e)}"
        )
    except Exception as e:
        import traceback
        print(f"[VALIDATE_PROGRAMME] Error: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error validating programme: {str(e)}"
        )
