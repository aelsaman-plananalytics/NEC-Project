"""
Acceptance record model: governance decisions on submissions.

Acceptance is a human/governance act. It does not modify acceptability,
validation output, or the audit trail. Acceptance records are append-only.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Literal

AcceptanceDecision = Literal["ACCEPT", "NOT_ACCEPT", "ACCEPT_WITH_COMMENTS"]

VALID_DECISIONS: frozenset = frozenset({"ACCEPT", "NOT_ACCEPT", "ACCEPT_WITH_COMMENTS"})


def create_acceptance_record(
    submission_id: str,
    project_id: str,
    decision: AcceptanceDecision,
    decided_by: str,
    comments: Optional[str] = None,
    acceptance_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build an acceptance record (does not persist). comments required if decision is ACCEPT_WITH_COMMENTS.
    """
    submission_id = (submission_id or "").strip()
    project_id = (project_id or "").strip()
    decision = (decision or "").strip().upper()
    if decision not in VALID_DECISIONS:
        raise RuntimeError(
            f"Acceptance decision must be one of {sorted(VALID_DECISIONS)}. Got {decision!r}."
        )
    if decision == "ACCEPT_WITH_COMMENTS":
        if not comments or not str(comments).strip():
            raise RuntimeError(
                "Acceptance decision ACCEPT_WITH_COMMENTS requires non-empty comments."
            )
    decided_by = (decided_by or "").strip()
    return {
        "acceptance_id": acceptance_id or str(uuid.uuid4()),
        "submission_id": submission_id,
        "project_id": project_id,
        "decision": decision,
        "comments": (comments or "").strip() if comments else None,
        "decided_by": decided_by,
        "decided_at": datetime.now(timezone.utc).isoformat(),
    }
