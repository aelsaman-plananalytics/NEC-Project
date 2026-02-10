"""
Planner Guidance & Submission Progression (Step 2B).

Composes existing API response + Step 2A evolution only. Read-only.
Does not modify, infer, or re-evaluate acceptability or evidence.
"""

from typing import Dict, List, Any, Optional, Set

from app.evolution.submission_evolution import build_submission_evolution

_ACCEPTABILITY = "acceptability_status"
_OBL_REPORT = "obligations_report"
_NOT_REP_MANDATORY = "obligations_not_represented_but_mandatory"
_STAGE = "submission_stage"

# API stage values for output (product contract)
STAGE_INITIAL = "initial"
STAGE_INTERIM = "interim"
STAGE_FINAL = "final"


def _normalize_stage(stage: Optional[str]) -> str:
    """Map submission_stage to initial | interim | final for output."""
    if not stage or not str(stage).strip():
        return STAGE_INITIAL
    s = str(stage).strip().lower()
    if s in ("initial", "first_programme", "first programme"):
        return STAGE_INITIAL
    if s in ("interim", "revised_programme", "revised programme"):
        return STAGE_INTERIM
    if s in ("final", "update"):
        return STAGE_FINAL
    return STAGE_INITIAL


def _obligation_name(ob: Dict[str, Any]) -> str:
    return (
        (ob.get("canonical_name") or ob.get("original_contract_text") or ob.get("id") or "")
    ).strip() or "—"


def build_planner_guidance(
    current_response: Dict[str, Any],
    previous_response: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build planner-facing guidance from current (and optional previous) API response.
    Composes build_submission_evolution + API fields only. No validator calls.
    """
    current = current_response or {}
    evolution = build_submission_evolution(current, previous_response=previous_response)

    summary = evolution["submission_evolution_summary"]
    current_acceptability = summary["current_acceptability"]
    status_change = summary["status_change"]
    current_blockers = list(evolution["current_blockers"])
    obligation_changes = evolution["obligation_changes"]

    not_rep = list(current.get(_NOT_REP_MANDATORY) or [])
    report_by_id = {r.get("id"): r for r in (current.get(_OBL_REPORT) or []) if r.get("id")}

    # ---- Safety: ACCEPTABLE => no blockers ----
    if current_acceptability == "ACCEPTABLE":
        if current_blockers:
            raise RuntimeError(
                "Planner guidance invariant: current_acceptability is ACCEPTABLE but current_blockers is non-empty. "
                f"Blockers: {[b.get('obligation_id') for b in current_blockers]}"
            )
        required_before: List[Dict[str, Any]] = []
    else:
        # ---- required_before_next_submission: all blockers with evidence_mode, canonical_match_string ----
        required_before = []
        for ob in not_rep:
            oid = ob.get("id")
            ra = ob.get("required_action")
            if ra is None or (isinstance(ra, str) and not ra.strip()):
                raise RuntimeError(
                    f"Planner guidance invariant: blocker obligation_id={oid!r} has no required_action. "
                    "Every blocker must have a required_action."
                )
            report_row = report_by_id.get(oid) or ob
            required_before.append({
                "obligation_id": oid,
                "obligation_name": _obligation_name(ob),
                "required_action": ob.get("required_action"),
                "evidence_mode": report_row.get("evidence_mode"),
                "canonical_match_string": report_row.get("canonical_match_string"),
            })

        # ---- Safety: obligation IDs consistent ----
        blocker_ids: Set[str] = {b["obligation_id"] for b in current_blockers if b.get("obligation_id")}
        required_ids: Set[str] = {r["obligation_id"] for r in required_before if r.get("obligation_id")}
        if blocker_ids != required_ids:
            raise RuntimeError(
                "Planner guidance invariant: obligation IDs in required_before_next_submission "
                f"must match obligations_not_represented_but_mandatory. "
                f"Blockers: {blocker_ids}, required: {required_ids}"
            )

    # ---- since_last_submission: resolved, new_blockers, unchanged_blockers ----
    resolved_obligations = list(obligation_changes["became_aligned"])

    prev_not_rep_ids: Set[str] = set()
    if previous_response:
        prev_not_rep_ids = {
            r.get("id") for r in (previous_response.get(_NOT_REP_MANDATORY) or []) if r.get("id")
        }

    new_blockers: List[Dict[str, Any]] = []
    unchanged_blockers: List[Dict[str, Any]] = []
    for b in current_blockers:
        oid = b.get("obligation_id")
        row = {"obligation_id": oid, "obligation_name": b.get("obligation_name"), "required_action": b.get("required_action")}
        if oid in prev_not_rep_ids:
            unchanged_blockers.append(row)
        else:
            new_blockers.append(row)

    since_last_submission = {
        "resolved_obligations": resolved_obligations,
        "new_blockers": new_blockers,
        "unchanged_blockers": unchanged_blockers,
    }

    advisory_notes = [
        "Planner assumptions are recorded for audit only and do not affect acceptability.",
        "Lifecycle expectations describe typical progression and do not relax Clause 31 requirements.",
    ]

    return {
        "planner_guidance": {
            "submission_stage": _normalize_stage(current.get(_STAGE)),
            "current_acceptability": current_acceptability,
            "status_change": status_change,
            "since_last_submission": since_last_submission,
            "required_before_next_submission": required_before,
            "advisory_notes": advisory_notes,
        }
    }
