"""
Validate Programme Router.

Validates Primavera P6 programme against NEC contract with comprehensive validation.
Supports both legacy contract JSON (extracted_clauses) and new analyze_contract output
(project, scope_items, programme_compliance_model, contract_dates, etc.).

API hardening: idempotency (Idempotency-Key), structured errors, /api/v1/ prefix, response_signature.
"""

import copy
import hashlib
import json
import re
import tempfile
import os
from pathlib import Path
import time
from datetime import datetime, date, timedelta
from typing import Optional, List, Any, Dict
from fastapi import APIRouter, UploadFile, File, Form, Request, status, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.auth import get_current_user_optional
from app.models.user import User
from app.models.analysis_run import AnalysisRun

from app.api_errors import (
    structured_error_response,
    error_code_from_runtime_error,
    BAD_REQUEST,
    NOT_FOUND,
    VALIDATION_GUARDRAIL_ERROR,
    LEDGER_INTEGRITY_ERROR,
    IDEMPOTENCY_CONFLICT,
    INTERNAL_ERROR,
    PLAN_LIMIT_EXCEEDED,
)
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
from app.runtime_paths import RUNTIME_DIR
from app.security_config import MAX_XER_FILE_SIZE_BYTES
from app.api_audit import log_api_request
from app.evolution.submission_evolution import build_submission_evolution
from app.guidance.planner_guidance import build_planner_guidance
from app.performance import run_with_timeout, XER_VALIDATION_TIMEOUT

router = APIRouter(
    prefix="/api",
    tags=["validation"],
)


def _validate_xer_upload(
    filename: Optional[str],
    content: bytes,
    *,
    field_hint: str = "xer_file",
) -> Optional[JSONResponse]:
    """Validate XER upload: .xer extension, non-empty, max size. Returns error response or None. Reused for xer_file and previous_xer_file."""
    if not filename or not str(filename).lower().endswith(".xer"):
        msg = "Programme data must be an XER file." if field_hint == "xer_file" else "Previous programme file must be an XER file."
        return structured_error_response(
            status.HTTP_400_BAD_REQUEST,
            BAD_REQUEST,
            msg,
            details=f"{field_hint} must have a .xer extension.",
        )
    if len(content) == 0:
        return structured_error_response(
            status.HTTP_400_BAD_REQUEST,
            BAD_REQUEST,
            "Empty upload.",
            details="XER file must not be empty.",
        )
    if len(content) > MAX_XER_FILE_SIZE_BYTES:
        return structured_error_response(
            status.HTTP_400_BAD_REQUEST,
            BAD_REQUEST,
            "File too large.",
            details={"max_bytes": MAX_XER_FILE_SIZE_BYTES, "received": len(content)},
        )
    return None


def _get_latest_analysis_json_path() -> Optional[Path]:
    """Return path to the latest JSON in runtime/analysis_reports, or None."""
    analysis_dir = RUNTIME_DIR / "analysis_reports"
    if not analysis_dir.exists():
        return None
    json_files = list(analysis_dir.glob("analysis_*.json"))
    if not json_files:
        return None
    return max(json_files, key=lambda p: p.stat().st_mtime)


def _idempotency_storage():
    """Storage for idempotency entries (idempotency/{key}.json)."""
    from app.storage import get_storage
    return get_storage()


def _sanitize_idempotency_key(key: str) -> str:
    """Allow only alphanumeric and hyphen for safe filenames."""
    return re.sub(r"[^a-zA-Z0-9\-]", "", (key or "")).strip() or "key"


def _payload_hash(
    xer_content: bytes,
    contract_canonical_bytes: bytes,
    submission_stage: Optional[str],
    planner_assumptions_form: Optional[str],
    previous_xer_content: Optional[bytes] = None,
) -> str:
    """Deterministic hash of request payload for idempotency. Includes previous_xer SHA256 only when provided (so same key + different previous → 409)."""
    payload = {
        "xer_sha256": hashlib.sha256(xer_content).hexdigest(),
        "contract_sha256": hashlib.sha256(contract_canonical_bytes).hexdigest(),
        "stage": (submission_stage or "").strip(),
        "assumptions": (planner_assumptions_form or "").strip(),
    }
    if previous_xer_content is not None:
        payload["previous_xer_sha256"] = hashlib.sha256(previous_xer_content).hexdigest()
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _idempotency_get(key: str) -> Optional[Dict[str, Any]]:
    """Load stored idempotency entry if present. Returns None if not found."""
    safe = _sanitize_idempotency_key(key)
    path = f"idempotency/{safe}.json"
    return _idempotency_storage().load_json(path)


def _idempotency_set(key: str, payload_hash: str, response: Dict[str, Any]) -> None:
    """Store idempotency entry: key -> { payload_hash, response }."""
    safe = _sanitize_idempotency_key(key)
    path = f"idempotency/{safe}.json"
    _idempotency_storage().save_json(path, {"payload_hash": payload_hash, "response": response})


def _response_signature(response_dict: Dict[str, Any]) -> str:
    """SHA-256 of normalized JSON (excluding response_signature and variable metadata). Deterministic for same validation result."""
    payload = copy.deepcopy(response_dict)
    payload.pop("response_signature", None)
    meta = payload.get("metadata") or {}
    if isinstance(meta, dict):
        # Exclude fields that vary per request so signature is deterministic for same outcome
        meta = {k: v for k, v in meta.items() if k not in ("validation_timestamp", "output_path", "output_filename")}
        payload["metadata"] = meta
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
    from app.performance import log_performance_metric, run_with_timeout, XER_VALIDATION_TIMEOUT

    temp_xer_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xer') as tmp:
            tmp.write(xer_content)
            temp_xer_path = tmp.name

        xer_loader = XERLoader()
        t0 = time.time()
        p6_data = xer_loader.load_xer(temp_xer_path)
        log_performance_metric("xer_parsing", (time.time() - t0) * 1000)

        logic_checker = LogicChecker()
        logic_checks = logic_checker.check_logic(p6_data)

        validator = ComprehensiveValidator()
        t1 = time.time()
        validation_output = validator.validate(contract_data, p6_data)
        log_performance_metric("validation", (time.time() - t1) * 1000)

        # Ensure submission_stage is available to the validator summary logic.
        # This is required for Clause 31 stage-based thresholds in _calculate_validation_summary().
        if submission_stage is not None:
            validation_output["submission_stage"] = submission_stage
            # Recompute summary once so stage-sensitive thresholds apply.
            validation_output["validation_summary"] = validator._calculate_validation_summary(validation_output)

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


# Deprecated: use POST /api/v1/validate_programme. Kept for backward compatibility.
@router.post("/validate_programme", deprecated=True, include_in_schema=False)
@router.post("/v1/validate_programme")
async def validate_programme(
    request: Request,
    xer_file: UploadFile = File(..., description="XER file from Primavera P6"),
    previous_xer_file: Optional[UploadFile] = File(None, description="Optional: previous programme as XER file (Primavera P6), for submission comparison only; not JSON"),
    json_file: Optional[UploadFile] = File(None, description="Optional: JSON from /api/analyze_contract; if omitted, latest from runtime/analysis_reports is used"),
    submission_stage_form: Optional[str] = Form(None, description="Optional: submission stage (e.g. first_programme, revised_programme, update) for lifecycle"),
    planner_assumptions_form: Optional[str] = Form(None, description="Optional: JSON array of { obligation_id, assumption_type, rationale } for planner-declared assumptions"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> JSONResponse:
    """
    Validate Primavera P6 programme against NEC contract.
    Use /api/v1/validate_programme for versioned API.
    Optional header: Idempotency-Key for idempotent requests.
    """
    idempotency_key: Optional[str] = request.headers.get("Idempotency-Key") or None
    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip() or None
    comparison_mode = "none"

    def _client_ip() -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host or "unknown"
        return "unknown"

    def _audit(status_code: int, response_signature: Optional[str] = None, comparison_mode: Optional[str] = None) -> None:
        log_api_request(
            ip=_client_ip(),
            route=request.scope.get("path") or "-",
            status_code=status_code,
            idempotency_key=idempotency_key,
            response_signature=response_signature,
            comparison_mode=comparison_mode,
        )

    if not xer_file.filename or not xer_file.filename.lower().endswith(".xer"):
        _audit(status.HTTP_400_BAD_REQUEST, comparison_mode=comparison_mode)
        return structured_error_response(
            status.HTTP_400_BAD_REQUEST,
            BAD_REQUEST,
            "Programme data must be an XER file.",
            details="xer_file must have a .xer extension.",
        )

    analysis_run_id: Optional[int] = None
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
                _audit(status.HTTP_400_BAD_REQUEST, comparison_mode=comparison_mode)
                return structured_error_response(
                    status.HTTP_400_BAD_REQUEST,
                    BAD_REQUEST,
                    "No contract JSON provided and no analysis report found.",
                    details="Upload a JSON file or run /api/analyze_contract first.",
                )
            print(f"[VALIDATE_PROGRAMME] Loading latest contract JSON: {latest_path.name}")
            with open(latest_path, 'r', encoding='utf-8') as f:
                contract_data = json.load(f)
            contract_source = latest_path.name
        
        # Accept both formats: legacy (extracted_clauses) or new (contract_dates / programme_compliance_model / project)
        if "extracted_clauses" not in contract_data and "contract_dates" not in contract_data and "programme_compliance_model" not in contract_data:
            _audit(status.HTTP_400_BAD_REQUEST, comparison_mode=comparison_mode)
            return structured_error_response(
                status.HTTP_400_BAD_REQUEST,
                BAD_REQUEST,
                "Invalid contract JSON.",
                details="Expected 'extracted_clauses' (legacy) or 'contract_dates' / 'programme_compliance_model' (analyze_contract output).",
            )

        # Reject stale obligation_entities so we never trust old artefacts (even before we overwrite them).
        _CURRENT_FROZEN_VERSION = 7
        oe = contract_data.get("obligation_entities") or {}
        if oe and isinstance(oe, dict) and (oe.get("frozen_requirements_version") or 0) < _CURRENT_FROZEN_VERSION:
            _audit(status.HTTP_400_BAD_REQUEST, comparison_mode=comparison_mode)
            return structured_error_response(
                status.HTTP_400_BAD_REQUEST,
                BAD_REQUEST,
                "Contract JSON has stale obligation_entities.",
                details=f"Re-run contract analysis to get version {_CURRENT_FROZEN_VERSION} (current: {oe.get('frozen_requirements_version', 0)}).",
            )

        # Plan gating: enforce monthly run limit for non-enterprise users (when authenticated)
        if current_user is not None:
            plan_type = (getattr(current_user, "plan_type", None) or "free").strip().lower()
            if plan_type != "enterprise":
                limit = getattr(current_user, "monthly_run_limit", None) or 10
                runs = getattr(current_user, "runs_this_month", None) or 0
                if runs >= limit:
                    _audit(status.HTTP_403_FORBIDDEN, comparison_mode=comparison_mode)
                    return structured_error_response(
                        status.HTTP_403_FORBIDDEN,
                        PLAN_LIMIT_EXCEEDED,
                        "Monthly run limit exceeded.",
                        details={"error_code": PLAN_LIMIT_EXCEEDED, "monthly_run_limit": limit},
                    )

        # LIFECYCLE INVARIANT: All obligation entities MUST be rebuilt at validation time using current
        # obligation-construction logic. Validation must NEVER trust obligation_entities stored in
        # the uploaded or latest analysis JSON (they were built at analysis time and can be stale).
        # Rebuilding here ensures obligations_report is derived from the current contract extraction
        # and that programmes missing mandatory obligations FAIL acceptability (single source of truth).
        try:
            # Preserve expected mandatory count from the uploaded artefact (internal only; not returned).
            # Used to fail closed if rebuild cannot reconstruct mandatory obligations.
            _pre_oe = contract_data.get("obligation_entities") or {}
            _pre_obligations = _pre_oe.get("obligations") if isinstance(_pre_oe, dict) else None
            if isinstance(_pre_obligations, list):
                contract_data["_expected_mandatory_obligations_count"] = sum(
                    1 for o in _pre_obligations if isinstance(o, dict) and o.get("mandatory_for_acceptance")
                )
            frozen = build_frozen_requirements(contract_data)
            contract_data["obligation_entities"] = frozen["obligation_entities"]
            contract_data["frozen_requirements"] = frozen["frozen_requirements"]
        except Exception as e:
            contract_data["obligation_entities"] = {"obligations": [], "validation_error": str(e)}
            contract_data["frozen_requirements"] = []

        # Layer 2: planner lifecycle — apply stage and merge assumptions (does not change acceptability logic)
        # API contract: accept "initial" | "interim" | "final" (and internal names); echo back for response
        submission_stage_api: Optional[str] = (submission_stage_form.strip() or None) if submission_stage_form else None
        submission_stage_internal = (
            submission_stage_form
            or submission_stage_api
            or "initial"
        )
        if not submission_stage_internal or str(submission_stage_internal).lower() == "string":
            submission_stage_internal = "initial"
        submission_stage_internal = str(submission_stage_internal).lower()

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
        err = _validate_xer_upload(xer_file.filename, xer_content, field_hint="xer_file")
        if err is not None:
            _audit(status.HTTP_400_BAD_REQUEST, comparison_mode=comparison_mode)
            return err

        # Optional previous programme for submission comparison (ephemeral; no persistence/ledger/audit)
        previous_xer_content: Optional[bytes] = None
        previous_xer_filename: Optional[str] = None
        if previous_xer_file and previous_xer_file.filename:
            prev_content = await previous_xer_file.read()
            err_prev = _validate_xer_upload(
                previous_xer_file.filename, prev_content, field_hint="previous_xer_file"
            )
            if err_prev is not None:
                _audit(status.HTTP_400_BAD_REQUEST, comparison_mode=comparison_mode)
                return err_prev
            previous_xer_content = prev_content
            previous_xer_filename = previous_xer_file.filename

        comparison_mode = "file_upload" if previous_xer_content else "none"

        contract_canonical_bytes = json.dumps(contract_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        payload_hash = _payload_hash(
            xer_content, contract_canonical_bytes, submission_stage_form, planner_assumptions_form, previous_xer_content
        )
        if idempotency_key:
            stored = _idempotency_get(idempotency_key)
            if stored and stored.get("payload_hash") == payload_hash:
                resp = stored["response"]
                _audit(status.HTTP_200_OK, resp.get("response_signature"), comparison_mode=comparison_mode)
                return JSONResponse(status_code=status.HTTP_200_OK, content=resp)
            if stored and stored.get("payload_hash") != payload_hash:
                _audit(status.HTTP_409_CONFLICT, comparison_mode=comparison_mode)
                return structured_error_response(
                    status.HTTP_409_CONFLICT,
                    IDEMPOTENCY_CONFLICT,
                    "Idempotency key already used with a different request payload.",
                    details={"idempotency_key": _sanitize_idempotency_key(idempotency_key)},
                )

        if current_user is not None:
            from app.routers.runs import _build_preferences_snapshot
            snapshot = _build_preferences_snapshot(current_user)
            run = AnalysisRun(
                user_id=current_user.id,
                contract_name=(contract_source or "Contract")[:512],
                programme_name=xer_file.filename[:512] if xer_file.filename else None,
                contract_analysis=None,
                validation_result=None,
                preferences_snapshot=snapshot,
                status="processing",
            )
            db.add(run)
            db.commit()
            db.refresh(run)
            analysis_run_id = run.id

        try:
            output_dict = run_with_timeout(
                lambda: _run_programme_validation(
                    contract_data, xer_content, xer_file.filename, contract_source,
                    submission_stage=submission_stage_internal,
                    obligation_readiness=obligation_readiness,
                ),
                XER_VALIDATION_TIMEOUT,
                "xer_validation",
            )
        except TimeoutError as e:
            if analysis_run_id is not None:
                _run = db.query(AnalysisRun).filter(
                    AnalysisRun.id == analysis_run_id,
                    AnalysisRun.user_id == current_user.id,
                ).first()
                if _run:
                    _run.status = "timed_out"
                    db.commit()
            _audit(status.HTTP_503_SERVICE_UNAVAILABLE, comparison_mode=comparison_mode)
            return structured_error_response(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                INTERNAL_ERROR,
                str(e),
                details={"error_code": "VALIDATION_TIMEOUT"},
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
        output_dict["submission_stage"] = submission_stage_internal

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

        # Submission comparison (observational only; does not affect acceptability or persistence)
        if previous_xer_content and previous_xer_filename:
            # In-memory validation for previous programme only; no persistence, audit, ledger, or idempotency
            try:
                previous_output = run_with_timeout(
                    lambda: _run_programme_validation(
                        contract_data,
                        previous_xer_content,
                        previous_xer_filename,
                        contract_source,
                        submission_stage=submission_stage_internal or submission_stage_api,
                        obligation_readiness=obligation_readiness,
                    ),
                    XER_VALIDATION_TIMEOUT,
                    "xer_validation_previous",
                )
            except TimeoutError:
                previous_output = None
            if previous_output is not None:
                prev_scope = (previous_output.get("alignment") or {}).get("scope_coverage") or {}
                prev_vs = previous_output.get("validation_summary") or {}
                previous_response = {
                    "acceptability_status": _normalize_acceptability(prev_vs.get("acceptability_status")),
                    "overall_status": prev_vs.get("overall_status"),
                    "obligations_report": prev_scope.get("obligations_report", []),
                    "obligations_not_represented_but_mandatory": prev_scope.get("obligations_not_represented_but_mandatory", []),
                    "submission_stage": submission_stage_api,
                }
                evolution = build_submission_evolution(output_dict, previous_response)
                build_planner_guidance(output_dict, previous_response)  # for consistency; not added to response
                output_dict["submission_comparison"] = {
                    "comparison_mode": "file_upload",
                    "previous_programme_name": previous_xer_filename,
                    "status_change": evolution["submission_evolution_summary"]["status_change"],
                    "became_aligned": evolution["obligation_changes"]["became_aligned"],
                    "became_unaligned": evolution["obligation_changes"]["became_unaligned"],
                }
            else:
                output_dict["submission_comparison"] = None
        else:
            output_dict["submission_comparison"] = None

        # Response signature (deterministic from normalized JSON; does not affect acceptability)
        output_dict["response_signature"] = _response_signature(output_dict)

        # Read-only schedule analytics (descriptive only; does not affect acceptability or response_signature)
        from app.reporting.float_analytics import compute_float_profile
        fp = compute_float_profile(output_dict.get("programme_summary") or {})
        if fp is not None:
            output_dict["float_profile"] = fp

        # Run lifecycle: update run to completed and attach validation_result
        if analysis_run_id is not None:
            _run = db.query(AnalysisRun).filter(
                AnalysisRun.id == analysis_run_id,
                AnalysisRun.user_id == current_user.id,
            ).first()
            if _run:
                _run.validation_result = output_dict
                _run.status = "completed"
                db.commit()
            output_dict["run_id"] = analysis_run_id

        # Plan gating: increment runs_this_month for authenticated user after successful validation
        if current_user is not None:
            today = date.today()
            reset_date = getattr(current_user, "runs_reset_date", None)
            if reset_date is not None and today > reset_date:
                current_user.runs_this_month = 0
                current_user.runs_reset_date = (today.replace(day=28) + timedelta(days=7)).replace(day=1)
            current_user.runs_this_month = (getattr(current_user, "runs_this_month", None) or 0) + 1
            if getattr(current_user, "runs_reset_date", None) is None:
                current_user.runs_reset_date = (today.replace(day=28) + timedelta(days=7)).replace(day=1)
            db.commit()

        # Save to runtime/validation_reports
        validation_dir = RUNTIME_DIR / "validation_reports"
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
        
        if idempotency_key:
            _idempotency_set(idempotency_key, payload_hash, output_dict)
        
        print(f"[VALIDATE_PROGRAMME] Validation results saved to: {output_path}")
        vs = output_dict.get("validation_summary", {})
        print(f"[VALIDATE_PROGRAMME] NEC Alignment Score: {vs.get('nec_alignment_score', 0)}%")
        print(f"[VALIDATE_PROGRAMME] Schedule Quality Score: {vs.get('schedule_quality_score', 0)}%")
        print(f"[VALIDATE_PROGRAMME] Overall Status: {vs.get('overall_status', 'unknown')}")
        _audit(status.HTTP_200_OK, output_dict.get("response_signature"), comparison_mode=comparison_mode)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=output_dict
        )
        
    except json.JSONDecodeError as e:
        _audit(status.HTTP_400_BAD_REQUEST, comparison_mode=comparison_mode)
        return structured_error_response(
            status.HTTP_400_BAD_REQUEST,
            BAD_REQUEST,
            "Invalid JSON format.",
            details=str(e),
        )
    except RuntimeError as e:
        if analysis_run_id is not None and current_user is not None:
            try:
                _run = db.query(AnalysisRun).filter(
                    AnalysisRun.id == analysis_run_id,
                    AnalysisRun.user_id == current_user.id,
                ).first()
                if _run:
                    _run.status = "failed"
                    db.commit()
            except Exception:
                pass
        import traceback
        print(f"[VALIDATE_PROGRAMME] RuntimeError: {str(e)}")
        print(traceback.format_exc())
        code = error_code_from_runtime_error(str(e))
        status_code = status.HTTP_400_BAD_REQUEST if code in (BAD_REQUEST, VALIDATION_GUARDRAIL_ERROR, NOT_FOUND) else status.HTTP_500_INTERNAL_SERVER_ERROR
        _audit(status_code, comparison_mode=comparison_mode)
        return structured_error_response(status_code, code, str(e), details=None)
    except Exception as e:
        if analysis_run_id is not None and current_user is not None:
            try:
                _run = db.query(AnalysisRun).filter(
                    AnalysisRun.id == analysis_run_id,
                    AnalysisRun.user_id == current_user.id,
                ).first()
                if _run:
                    _run.status = "failed"
                    db.commit()
            except Exception:
                pass
        import traceback
        print(f"[VALIDATE_PROGRAMME] Error: {str(e)}")
        print(traceback.format_exc())
        _audit(status.HTTP_500_INTERNAL_SERVER_ERROR, comparison_mode=comparison_mode)
        return structured_error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            INTERNAL_ERROR,
            f"Error validating programme: {str(e)}",
            details=None,
        )
