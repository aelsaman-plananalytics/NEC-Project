"""
Submission lifecycle layer (Layer 2). See backend/ACCEPTABILITY_INVARIANT.md.

Consumes acceptability results; never overrides or reinterprets them.
Provides: submission stages, maturity expectations, obligation readiness, planner assumptions merge.
"""

from typing import Dict, List, Any, Optional

# Clause 31 submission stages (order matters for "required from" logic)
SUBMISSION_STAGE_FIRST_PROGRAMME = "first_programme"
SUBMISSION_STAGE_REVISED_PROGRAMME = "revised_programme"
SUBMISSION_STAGE_UPDATE = "update"

SUBMISSION_STAGE_ORDER = [
    SUBMISSION_STAGE_FIRST_PROGRAMME,
    SUBMISSION_STAGE_REVISED_PROGRAMME,
    SUBMISSION_STAGE_UPDATE,
]

STAGE_ORDER_INDEX = {s: i for i, s in enumerate(SUBMISSION_STAGE_ORDER)}

# API-facing stage names (product contract): map to internal stage for logic
SUBMISSION_STAGE_INITIAL = "initial"
SUBMISSION_STAGE_INTERIM = "interim"
SUBMISSION_STAGE_FINAL = "final"
API_STAGE_TO_INTERNAL = {
    SUBMISSION_STAGE_INITIAL: SUBMISSION_STAGE_FIRST_PROGRAMME,
    SUBMISSION_STAGE_INTERIM: SUBMISSION_STAGE_REVISED_PROGRAMME,
    SUBMISSION_STAGE_FINAL: SUBMISSION_STAGE_UPDATE,
    SUBMISSION_STAGE_FIRST_PROGRAMME: SUBMISSION_STAGE_FIRST_PROGRAMME,
    SUBMISSION_STAGE_REVISED_PROGRAMME: SUBMISSION_STAGE_REVISED_PROGRAMME,
    SUBMISSION_STAGE_UPDATE: SUBMISSION_STAGE_UPDATE,
}


def normalize_submission_stage(api_stage: Optional[str]) -> Optional[str]:
    """
    Map API stage (initial | interim | final) to internal stage (first_programme | revised_programme | update).
    Returns None if api_stage is empty; otherwise returns internal stage string for lifecycle logic.
    """
    if not api_stage or not str(api_stage).strip():
        return None
    key = str(api_stage).strip().lower()
    return API_STAGE_TO_INTERNAL.get(key, key)

# Allowed assumption types (must match validator EXPLICIT_ASSUMPTION_VALUES)
ASSUMPTION_COVERED_BY_LATER = "covered_by_later_submission"
ASSUMPTION_CLIENT_RESPONSIBILITY = "client_responsibility"
ASSUMPTION_OUT_OF_SCOPE = "out_of_scope_at_this_stage"

VALID_ASSUMPTION_TYPES = frozenset({ASSUMPTION_COVERED_BY_LATER, ASSUMPTION_CLIENT_RESPONSIBILITY, ASSUMPTION_OUT_OF_SCOPE})


def _stage_index(stage: Optional[str]) -> int:
    """Return numeric index for stage; unknown stages sort after known."""
    if not stage or not isinstance(stage, str):
        return -1
    return STAGE_ORDER_INDEX.get(stage.strip().lower(), len(SUBMISSION_STAGE_ORDER))


def get_stage_expectations(stage: Optional[str]) -> str:
    """Maturity expectations for a submission stage (explanatory only; does not affect acceptability)."""
    if not stage:
        return "Submission stage not specified; all obligations are evaluated for this submission."
    s = stage.strip().lower()
    if s == SUBMISSION_STAGE_FIRST_PROGRAMME:
        return "First programme submission: programme should demonstrate key dates, scope coverage, and constraint acknowledgement. Outstanding items may be planned for later submissions."
    if s == SUBMISSION_STAGE_REVISED_PROGRAMME:
        return "Revised programme: expectations build on first submission; previously deferred items may become mandatory."
    if s == SUBMISSION_STAGE_UPDATE:
        return "Programme update: full obligation set is typically in scope; deferrals should be explicitly assumed."
    return f"Stage '{stage}': obligations are evaluated per their required_from_stage and explicit assumptions."


def apply_stage_to_obligations(
    obligations: List[Dict[str, Any]],
    current_stage: Optional[str],
) -> List[Dict[str, Any]]:
    """
    For stage-aware activation: set mandatory_for_acceptance to False for obligations
    whose required_from_stage is after current_stage. Does not change alignment logic;
    the acceptability engine still receives obligations and evaluates only those with
    mandatory_for_acceptance True.
    Returns a new list of obligation dicts (shallow copy) so original is unchanged.
    """
    if not current_stage or _stage_index(current_stage) < 0:
        return list(obligations)
    current_idx = _stage_index(current_stage)
    out = []
    for ob in obligations:
        ob_copy = {**ob}
        required_from = ob.get("required_from_stage")
        if required_from is not None and str(required_from).strip():
            required_idx = _stage_index(str(required_from).strip())
            if required_idx > current_idx:
                ob_copy["mandatory_for_acceptance"] = False
        out.append(ob_copy)
    return out


def merge_planner_assumptions(
    obligations: List[Dict[str, Any]],
    planner_assumptions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Merge planner-declared assumptions into obligations by obligation_id.
    Each assumption: { "obligation_id": str, "assumption_type": str, "rationale": str (optional) }.
    assumption_type must be one of VALID_ASSUMPTION_TYPES.
    Returns a new list; does not change alignment rules (validator still applies WBS_ONLY etc.).
    """
    if not planner_assumptions:
        return list(obligations)
    by_id: Dict[str, Dict[str, Any]] = {}
    for a in planner_assumptions:
        if not isinstance(a, dict):
            continue
        ob_id = (a.get("obligation_id") or a.get("ob_id") or "").strip()
        atype = (a.get("assumption_type") or a.get("type") or "").strip().lower()
        if not ob_id or atype not in VALID_ASSUMPTION_TYPES:
            continue
        by_id[ob_id] = {"assumption_type": atype, "rationale": a.get("rationale") or ""}
    if not by_id:
        return list(obligations)
    out = []
    for ob in obligations:
        ob_copy = {**ob}
        oid = (ob.get("id") or "").strip()
        if oid in by_id:
            ob_copy["explicit_assumption"] = by_id[oid]["assumption_type"]
            if by_id[oid].get("rationale") and "rationale" not in ob_copy:
                ob_copy["assumption_rationale"] = by_id[oid]["rationale"]
        out.append(ob_copy)
    return out


def compute_obligation_readiness(
    obligations: List[Dict[str, Any]],
    current_stage: Optional[str],
) -> List[Dict[str, Any]]:
    """
    Compute per-obligation readiness for reporting: required_now, required_from_stage.
    Does not affect acceptability. When current_stage is None, required_now = mandatory_for_acceptance.
    """
    result = []
    for ob in obligations:
        oid = ob.get("id") or ""
        required_from = ob.get("required_from_stage")
        if not current_stage:
            required_now = bool(ob.get("mandatory_for_acceptance"))
        else:
            current_idx = _stage_index(current_stage)
            required_from_idx = _stage_index(required_from) if required_from else 0
            if required_from_idx < 0:
                required_from_idx = 0
            required_now = bool(ob.get("mandatory_for_acceptance")) and (current_idx >= required_from_idx)
        result.append({
            "obligation_id": oid,
            "required_now": required_now,
            "required_from_stage": (required_from or "").strip() or None,
            "obligation_name": ob.get("canonical_name") or ob.get("original_contract_text") or "",
        })
    return result


def prepare_contract_for_validation(
    contract_data: Dict[str, Any],
    submission_stage: Optional[str] = None,
    planner_assumptions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Prepare obligation_entities for validation: apply stage and merge assumptions.
    Returns a copy of contract_data with obligation_entities.obligations updated.
    Does not modify acceptability logic; only adjusts which obligations are mandatory this run
    and what explicit_assumption they carry.
    """
    out = {**contract_data}
    oe = out.get("obligation_entities") or {}
    obligations = list(oe.get("obligations") or [])
    if not obligations:
        return out
    obligations = apply_stage_to_obligations(obligations, submission_stage)
    obligations = merge_planner_assumptions(obligations, planner_assumptions or [])
    out["obligation_entities"] = {**oe, "obligations": obligations}
    return out
