"""
API response contract for /api/validate_programme.

Authoritative fields (decision-making, legally binding) are set ONLY by the validator.
They must never be inferred or recomputed in the router or report builder.
No confidence, narrative, or advisory data may affect them.

Planner/lifecycle guidance fields are non-authoritative and must never affect acceptability.
See backend/ACCEPTABILITY_INVARIANT.md.
"""

from typing import Dict, List, Any, Optional

# Authoritative: single source is validator output. Router MUST only copy, never compute.
AUTHORITATIVE_TOP_LEVEL = frozenset({
    "acceptability_status",
    "overall_status",
    "submission_stage",
    "obligations_report",
    "obligations_not_represented_but_mandatory",
    "scope_evidence_table",
})

# Guidance: may exist only as planner/lifecycle help; must never override evidence or acceptability.
GUIDANCE_TOP_LEVEL = frozenset({
    "lifecycle_expectations",
    "obligation_readiness",
    "planner_assumptions_used",
})


def enrich_obligation_readiness_with_report(
    readiness: List[Dict[str, Any]],
    obligations_report: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Merge aligned and required_action from obligations_report into each readiness item by obligation_id.
    Does not change acceptability; only enriches planner guidance for display.
    """
    by_id: Dict[str, Dict[str, Any]] = {}
    for r in obligations_report or []:
        oid = (r.get("id") or "").strip()
        if oid:
            by_id[oid] = {
                "aligned": r.get("aligned") is True,
                "required_action": r.get("required_action"),
            }
    out = []
    for item in readiness or []:
        oid = (item.get("obligation_id") or "").strip()
        merged = {**item}
        if oid in by_id:
            merged["aligned"] = by_id[oid]["aligned"]
            merged["required_action"] = by_id[oid]["required_action"]
        else:
            merged.setdefault("aligned", False)
            merged.setdefault("required_action", None)
        out.append(merged)
    return out


def _normalize_acceptability(v: Optional[str]) -> Optional[str]:
    """Product API contract: ACCEPTABLE | NOT_ACCEPTABLE. Validator may return 'NOT ACCEPTABLE'."""
    if v is None:
        return None
    return "NOT_ACCEPTABLE" if v == "NOT ACCEPTABLE" else v


def assert_acceptability_authority(
    validation_summary: Dict[str, Any],
    acceptability_status: Optional[str],
    overall_status: Optional[str],
) -> None:
    """
    Fail fast if authoritative fields were set from anywhere other than validation_summary.
    Call after copying acceptability_status and overall_status from validation_summary only.
    Accepts API-normalized acceptability (NOT_ACCEPTABLE) as matching validator "NOT ACCEPTABLE".
    """
    vs = validation_summary or {}
    raw_expected = vs.get("acceptability_status")
    expected_acceptability = _normalize_acceptability(raw_expected) if raw_expected else raw_expected
    expected_overall = vs.get("overall_status")
    if acceptability_status is not None and expected_acceptability is not None and acceptability_status != expected_acceptability:
        raise RuntimeError(
            "API contract violation: acceptability_status must come only from validator validation_summary. "
            f"Expected {expected_acceptability!r}, got {acceptability_status!r}."
        )
    if overall_status is not None and expected_overall is not None and overall_status != expected_overall:
        raise RuntimeError(
            "API contract violation: overall_status must come only from validator validation_summary. "
            f"Expected {expected_overall!r}, got {overall_status!r}."
        )
