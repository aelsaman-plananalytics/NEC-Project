"""
Programme Review Pack builder: assembles read-only payload from persisted outputs only.

Consumes SubmissionStore and AcceptanceStore. No validator, no evidence re-evaluation,
no inference. Presentation contract for PM review, supervisor acceptance, and audit export.
"""

from typing import Dict, List, Any, Optional

from app.persistence.submission_store import SubmissionStore, _normalize_acceptability
from app.persistence.acceptance_store import AcceptanceStore

_ACCEPTABILITY = "acceptability_status"
_OBL_REPORT = "obligations_report"
_NOT_REP_MANDATORY = "obligations_not_represented_but_mandatory"


def _obligation_name(ob: Dict[str, Any]) -> str:
    return (
        (ob.get("canonical_name") or ob.get("original_contract_text") or ob.get("id") or "")
    ).strip() or "—"


def build_programme_review_pack(
    submission_id: str,
    submission_store: SubmissionStore,
    acceptance_store: AcceptanceStore,
) -> Dict[str, Any]:
    """
    Assemble a single, structured, read-only Programme Review Pack from stored
    submission and acceptance records only. No validation or inference.
    """
    submission_id = (submission_id or "").strip()
    submission = submission_store.get(submission_id)
    if submission is None:
        raise RuntimeError(
            f"Programme review pack requires an existing submission. submission_id={submission_id!r} not found."
        )

    # Guard: planner_guidance and diagnostics must be present (persistence breach if missing)
    planner_guidance_output = submission.get("planner_guidance_output")
    diagnostics_output = submission.get("diagnostics_output")
    if planner_guidance_output is None:
        raise RuntimeError(
            "Programme review pack guard: planner_guidance_output is missing from submission. "
            "This indicates a persistence breach."
        )
    if diagnostics_output is None:
        raise RuntimeError(
            "Programme review pack guard: diagnostics_output is missing from submission. "
            "This indicates a persistence breach."
        )

    vr = submission.get("validation_response") or {}
    acceptability_status = _normalize_acceptability(vr.get(_ACCEPTABILITY))
    overall_status = (vr.get("overall_status") or "fail").strip()

    obligations_report = list(vr.get(_OBL_REPORT) or [])
    not_represented_raw = list(vr.get(_NOT_REP_MANDATORY) or [])

    # Guard 1: ACCEPTABLE and not_represented non-empty → RuntimeError
    if acceptability_status == "ACCEPTABLE" and not_represented_raw:
        raise RuntimeError(
            "Programme review pack guard: acceptability_status is ACCEPTABLE but "
            "obligations_not_represented_but_mandatory is non-empty. Contradiction not allowed."
        )

    # Mandatory obligations status from stored obligations_report only (no inference)
    total_mandatory = sum(1 for r in obligations_report if r.get("mandatory_for_acceptance") is True)
    aligned = sum(
        1 for r in obligations_report
        if r.get("mandatory_for_acceptance") is True and r.get("aligned") is True
    )
    not_aligned = total_mandatory - aligned

    not_represented: List[Dict[str, Any]] = []
    report_by_id = {r.get("id"): r for r in obligations_report if r.get("id")}
    for ob in not_represented_raw:
        oid = ob.get("id")
        report_row = report_by_id.get(oid) or ob
        not_represented.append({
            "obligation_id": oid,
            "obligation_name": _obligation_name(ob),
            "evidence_mode": report_row.get("evidence_mode"),
            "canonical_match_string": report_row.get("canonical_match_string"),
            "required_action": ob.get("required_action"),
        })

    # Guard 2: counts must reconcile with obligations_report
    if len(not_represented) != not_aligned:
        raise RuntimeError(
            "Programme review pack guard: mandatory_obligations_status counts do not reconcile. "
            f"not_represented count={len(not_represented)}, not_aligned={not_aligned}. "
            "Counts must match obligations_report."
        )

    acceptance_records = acceptance_store.get_by_submission(submission_id)
    for rec in acceptance_records:
        if (rec.get("submission_id") or "").strip() != submission_id:
            raise RuntimeError(
                "Programme review pack guard: acceptance_history references submission_id "
                f"{rec.get('submission_id')!r} which does not match requested submission_id={submission_id!r}."
            )

    latest_acceptance_decision: Optional[str] = None
    latest_acceptance_comments: Optional[str] = None
    if acceptance_records:
        latest = acceptance_records[-1]
        latest_acceptance_decision = (latest.get("decision") or "").strip() or None
        latest_acceptance_comments = (latest.get("comments") or "").strip() or None

    acceptance_history = [
        {
            "decision": (r.get("decision") or "").strip(),
            "comments": (r.get("comments") or "").strip() if r.get("comments") else None,
            "decided_by": (r.get("decided_by") or "").strip(),
            "decided_at": r.get("decided_at"),
        }
        for r in acceptance_records
    ]

    return {
        "review_metadata": {
            "submission_id": submission.get("submission_id"),
            "project_id": submission.get("project_id"),
            "programme_name": submission.get("programme_name"),
            "submission_stage": submission.get("submission_stage"),
            "created_at": submission.get("created_at"),
            "previous_submission_id": submission.get("previous_submission_id"),
        },
        "acceptability_section": {
            "acceptability_status": acceptability_status,
            "overall_status": overall_status,
            "legal_note": "Acceptability is determined solely under Clause 31 and is not altered by planner guidance or acceptance decisions.",
        },
        "mandatory_obligations_status": {
            "total_mandatory": total_mandatory,
            "aligned": aligned,
            "not_aligned": not_aligned,
            "not_represented": not_represented,
        },
        "planner_guidance": planner_guidance_output,
        "submission_evolution": submission.get("evolution_output"),
        "diagnostics_summary": diagnostics_output,
        "governance": {
            "latest_acceptance_decision": latest_acceptance_decision,
            "latest_acceptance_comments": latest_acceptance_comments,
            "acceptance_history": acceptance_history,
            "governance_note": "Acceptance decisions are governance actions and do not alter acceptability.",
        },
    }
