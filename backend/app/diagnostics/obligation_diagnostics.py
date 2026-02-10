"""
Obligation diagnostics: read-only UX truth layer.

Consumes API validation response only. Does not modify, infer, or recompute
acceptability. Surfaces verbatim: required_action, evidence_mode, canonical_match_string.
Assumptions are shown and explicitly marked as non-acceptability-affecting.
"""

from typing import Dict, List, Any, Optional

# Keys we read from the API response (no others)
_ACCEPTABILITY = "acceptability_status"
_OVERALL = "overall_status"
_OBL_REPORT = "obligations_report"
_NOT_REP_MANDATORY = "obligations_not_represented_but_mandatory"
_READINESS = "obligation_readiness"
_ASSUMPTIONS = "planner_assumptions_used"
_STAGE = "submission_stage"


def build_obligation_diagnostics(
    validation_response: Dict[str, Any],
    previous_response: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build read-only diagnostics from validation response.

    Uses only fields already present in the API response. No inference of
    evidence, alignment, or confidence. Does not override acceptability_status
    or overall_status.

    Returns:
        diagnostics_summary: Deterministic explanation text.
        failure_table: One row per mandatory unaligned obligation (from
            obligations_not_represented_but_mandatory only).
        planner_checklist: Items derived only from required_action for those
            obligations.
        submission_diff: When previous_response is provided, aligned/unaligned
            transitions only (from obligations_report.aligned).
        planner_assumptions_note: Assumptions listed with note that they do
            not affect acceptability.
    """
    resp = validation_response or {}
    not_rep = list(resp.get(_NOT_REP_MANDATORY) or [])
    acceptability = (resp.get(_ACCEPTABILITY) or "").strip()
    # Normalize validator output spelling for comparison
    is_acceptable = acceptability == "ACCEPTABLE"

    # ---- diagnostics_summary (deterministic) ----
    if is_acceptable:
        diagnostics_summary = "Acceptable. All mandatory obligations are represented."
    else:
        n = len(not_rep)
        diagnostics_summary = (
            f"Not acceptable. {n} mandatory obligation(s) not represented."
        )

    # ---- failure_table: only obligations_not_represented_but_mandatory ----
    failure_table: List[Dict[str, Any]] = []
    for ob in not_rep:
        failure_table.append({
            "obligation_id": ob.get("id"),
            "original_contract_text": ob.get("original_contract_text"),
            "canonical_name": ob.get("canonical_name"),
            "evidence_mode": ob.get("evidence_mode"),
            "canonical_match_string": ob.get("canonical_match_string"),
            "required_action": ob.get("required_action"),
            "explicit_assumption": ob.get("explicit_assumption"),
            "explicit_assumption_note": (
                "Planner assumption is for visibility only; it does not affect acceptability."
                if ob.get("explicit_assumption") else None
            ),
        })

    # ---- planner_checklist: derived only from required_action for blockers ----
    planner_checklist: List[Dict[str, Any]] = []
    for ob in not_rep:
        ra = ob.get("required_action")
        planner_checklist.append({
            "obligation_id": ob.get("id"),
            "required_action": ra,
            "obligation_name": ob.get("original_contract_text") or ob.get("canonical_name"),
        })

    # ---- submission_diff: only when previous_response provided ----
    submission_diff: Optional[Dict[str, Any]] = None
    if previous_response is not None:
        curr_report = resp.get(_OBL_REPORT) or []
        prev_report = previous_response.get(_OBL_REPORT) or []
        curr_aligned = {r["id"] for r in curr_report if r.get("aligned") is True}
        prev_aligned = {r["id"] for r in prev_report if r.get("aligned") is True}
        became_aligned_ids = curr_aligned - prev_aligned
        became_unaligned_ids = prev_aligned - curr_aligned

        def _rows_by_id(report: List[Dict], ids: set) -> List[Dict[str, Any]]:
            by_id = {r.get("id"): r for r in report if r.get("id")}
            return [
                {"id": i, "original_contract_text": by_id.get(i, {}).get("original_contract_text")}
                for i in sorted(ids) if i in by_id
            ]

        submission_diff = {
            "became_aligned": _rows_by_id(curr_report, became_aligned_ids),
            "became_unaligned": _rows_by_id(prev_report, became_unaligned_ids),
        }

    # ---- assumptions: shown with non-acceptability note ----
    assumptions_raw = list(resp.get(_ASSUMPTIONS) or [])
    planner_assumptions_note = {
        "planner_assumptions_used": assumptions_raw,
        "note": "Planner assumptions are for visibility only and do not affect acceptability.",
    }

    return {
        "diagnostics_summary": diagnostics_summary,
        "failure_table": failure_table,
        "planner_checklist": planner_checklist,
        "submission_diff": submission_diff,
        "planner_assumptions_note": planner_assumptions_note,
        "acceptability_status": resp.get(_ACCEPTABILITY),
        "overall_status": resp.get(_OVERALL),
        "submission_stage": resp.get(_STAGE),
    }
