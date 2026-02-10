"""
Submission Evolution Engine: compare two validation API responses.

Tracks how a programme evolves across submissions (Clause 31 lifecycle).
Acceptability is read-only; never re-evaluated or inferred.
"""

from typing import Dict, List, Any, Optional

_ACCEPTABILITY = "acceptability_status"
_OBL_REPORT = "obligations_report"
_NOT_REP_MANDATORY = "obligations_not_represented_but_mandatory"


def _normalize_acceptability(status: Optional[str]) -> str:
    """Return ACCEPTABLE | NOT_ACCEPTABLE for output contract."""
    if not status or not str(status).strip():
        return "NOT_ACCEPTABLE"
    s = str(status).strip()
    if s == "NOT ACCEPTABLE":
        return "NOT_ACCEPTABLE"
    if s == "NOT_ACCEPTABLE":
        return "NOT_ACCEPTABLE"
    if s == "ACCEPTABLE":
        return "ACCEPTABLE"
    return "NOT_ACCEPTABLE"


def _obligation_name(ob: Dict[str, Any]) -> str:
    """Name for display from obligation dict."""
    return (
        (ob.get("canonical_name") or ob.get("original_contract_text") or ob.get("id") or "")
    ).strip() or "—"


def build_submission_evolution(
    current_response: Dict[str, Any],
    previous_response: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Compare current and previous validation responses. Read-only; does not
    re-run validation or change acceptability_status / overall_status.

    Inputs: only fields already present in API response (acceptability_status,
    obligations_report[].id|aligned|mandatory_for_acceptance|canonical_name|
    original_contract_text|evidence_mode|required_action,
    obligations_not_represented_but_mandatory[], obligation_readiness, etc.).

    Returns: submission_evolution_summary, obligation_changes, current_blockers,
    planner_guidance (deterministic, no confidence or scoring).
    """
    current = current_response or {}
    previous = previous_response

    curr_acceptability = _normalize_acceptability(current.get(_ACCEPTABILITY))
    prev_acceptability: Optional[str] = None
    if previous is not None:
        prev_acceptability = _normalize_acceptability(previous.get(_ACCEPTABILITY))

    # ---- status_change ----
    if previous is None:
        status_change = "FIRST_SUBMISSION"
    elif curr_acceptability == prev_acceptability:
        status_change = "UNCHANGED"
    elif curr_acceptability == "ACCEPTABLE" and prev_acceptability == "NOT_ACCEPTABLE":
        status_change = "BECAME_ACCEPTABLE"
    elif curr_acceptability == "NOT_ACCEPTABLE" and prev_acceptability == "ACCEPTABLE":
        status_change = "BECAME_NOT_ACCEPTABLE"
    else:
        status_change = "UNCHANGED"

    submission_evolution_summary = {
        "current_acceptability": curr_acceptability,
        "previous_acceptability": prev_acceptability,
        "status_change": status_change,
    }

    # ---- obligation_changes: compare obligations_report by id, aligned ----
    curr_report = list(current.get(_OBL_REPORT) or [])
    prev_report = list(previous.get(_OBL_REPORT) or []) if previous else []
    curr_by_id = {r.get("id"): r for r in curr_report if r.get("id")}
    prev_by_id = {r.get("id"): r for r in prev_report if r.get("id")}

    became_aligned: List[Dict[str, Any]] = []
    became_unaligned: List[Dict[str, Any]] = []
    if previous is not None:
        all_ids = set(curr_by_id) | set(prev_by_id)
        for oid in sorted(all_ids):
            c = curr_by_id.get(oid)
            p = prev_by_id.get(oid)
            c_aligned = c.get("aligned") is True if c else False
            p_aligned = p.get("aligned") is True if p else False
            if not p_aligned and c_aligned:
                became_aligned.append({
                    "obligation_id": oid,
                    "obligation_name": _obligation_name(c or p or {}),
                })
            elif p_aligned and not c_aligned:
                became_unaligned.append({
                    "obligation_id": oid,
                    "obligation_name": _obligation_name(c or p or {}),
                })

    obligation_changes = {
        "became_aligned": became_aligned,
        "became_unaligned": became_unaligned,
    }

    # ---- current_blockers: ONLY from obligations_not_represented_but_mandatory ----
    not_rep = list(current.get(_NOT_REP_MANDATORY) or [])
    current_blockers: List[Dict[str, Any]] = []
    for ob in not_rep:
        current_blockers.append({
            "obligation_id": ob.get("id"),
            "obligation_name": _obligation_name(ob),
            "required_action": ob.get("required_action"),
        })

    # ---- planner_guidance: deterministic summary and next_actions from required_action ----
    next_actions: List[str] = []
    for ob in not_rep:
        ra = ob.get("required_action")
        if ra and str(ra).strip():
            next_actions.append(str(ra).strip())

    n_became = len(became_aligned)
    n_became_unaligned = len(became_unaligned)
    n_blockers = len(current_blockers)

    if status_change == "FIRST_SUBMISSION":
        if curr_acceptability == "ACCEPTABLE":
            summary_text = "First submission. All mandatory obligations are represented."
        else:
            summary_text = (
                f"First submission. The programme is not acceptable due to {n_blockers} unresolved mandatory obligation(s)."
            )
    elif status_change == "BECAME_ACCEPTABLE":
        summary_text = (
            f"Since the previous submission, {n_became} mandatory obligation(s) are now represented. "
            "The programme is acceptable."
        )
    elif status_change == "BECAME_NOT_ACCEPTABLE":
        summary_text = (
            f"Since the previous submission, {n_became_unaligned} mandatory obligation(s) are no longer represented. "
            f"The programme is not acceptable due to {n_blockers} unresolved mandatory obligation(s)."
        )
    elif status_change == "UNCHANGED":
        if curr_acceptability == "ACCEPTABLE":
            summary_text = "No change since the previous submission. The programme remains acceptable."
        else:
            summary_text = (
                f"No change since the previous submission. "
                f"The programme remains not acceptable due to {n_blockers} unresolved mandatory obligation(s)."
            )
    else:
        summary_text = (
            f"The programme is not acceptable due to {n_blockers} unresolved mandatory obligation(s)."
        )

    planner_guidance = {
        "summary_text": summary_text,
        "next_actions": next_actions,
    }

    return {
        "submission_evolution_summary": submission_evolution_summary,
        "obligation_changes": obligation_changes,
        "current_blockers": current_blockers,
        "planner_guidance": planner_guidance,
    }
