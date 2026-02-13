"""
Acceptance summary: governance view for a submission.

Read-only. Does not alter acceptability or validation. Uses stored submission
and acceptance records only.
"""

from typing import Dict, List, Any, Optional

from app.persistence.submission_store import SubmissionStore, _normalize_acceptability


def build_acceptance_summary(
    submission_id: str,
    submission_store: Optional[SubmissionStore] = None,
    acceptance_store: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Build acceptance summary for a submission. acceptability_status comes from
    stored submission only. latest_acceptance_decision is the most recent
    acceptance record by decided_at; acceptance_history is full list ordered by decided_at.
    """
    submission_id = (submission_id or "").strip()
    sub_store = submission_store or SubmissionStore()
    if acceptance_store is None:
        from app.persistence.acceptance_store import AcceptanceStore
        acceptance_store = AcceptanceStore(submission_store=sub_store)
    acc_store = acceptance_store

    submission = sub_store.get(submission_id)
    acceptability_status: Optional[str] = None
    if submission:
        vr = submission.get("validation_response") or {}
        acceptability_status = _normalize_acceptability(vr.get("acceptability_status"))

    history: List[Dict[str, Any]] = acc_store.get_by_submission(submission_id)
    latest_acceptance_decision: Optional[Dict[str, Any]] = None
    if history:
        latest_acceptance_decision = history[-1]

    return {
        "submission_id": submission_id,
        "acceptability_status": acceptability_status,
        "latest_acceptance_decision": latest_acceptance_decision,
        "acceptance_history": history,
        "note": "Acceptance decisions are governance actions and do not alter acceptability.",
    }
