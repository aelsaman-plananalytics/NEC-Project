"""
Acceptance record persistence: immutable, write-once.

Acceptance records are immutable for governance audit. Any attempt to overwrite
an existing acceptance_id raises RuntimeError. No updates, no deletes.
Corrections require a new acceptance record.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional

from app.governance.acceptance_records import VALID_DECISIONS
from app.persistence.submission_store import SubmissionStore


def _validate_acceptance_guardrails(
    record: Dict[str, Any],
    submission_store: SubmissionStore,
) -> None:
    """Raise RuntimeError if record is invalid or submission does not exist."""
    submission_id = (record.get("submission_id") or "").strip()
    if not submission_id:
        raise RuntimeError("Acceptance record must have submission_id.")

    # Guard: submission must exist in SubmissionStore (and pass persistence guardrails on load)
    submission = submission_store.get(submission_id)
    if submission is None:
        raise RuntimeError(
            f"Acceptance references submission_id={submission_id!r} which does not exist in SubmissionStore. "
            "Acceptance must reference exactly one existing submission."
        )

    decision = (record.get("decision") or "").strip().upper()
    if decision not in VALID_DECISIONS:
        raise RuntimeError(
            f"Acceptance decision must be one of {sorted(VALID_DECISIONS)}. Got {decision!r}."
        )

    if decision == "ACCEPT_WITH_COMMENTS":
        comments = record.get("comments")
        if not comments or not str(comments).strip():
            raise RuntimeError(
                "Acceptance decision ACCEPT_WITH_COMMENTS requires non-empty comments."
            )


class AcceptanceStore:
    """
    File-backed immutable acceptance store. Write-once per acceptance_id.
    Acceptance records are immutable for governance audit purposes.
    """

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        submission_store: Optional[SubmissionStore] = None,
    ):
        if base_dir is None:
            base_dir = Path(__file__).parent.parent / "outputs" / "acceptance_history"
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)
        self._submission_store = submission_store or SubmissionStore()

    def _path(self, acceptance_id: str) -> Path:
        safe_id = "".join(c for c in acceptance_id if c.isalnum() or c == "-")
        if not safe_id:
            safe_id = "unknown"
        return self._base / f"{safe_id}.json"

    def save_acceptance(self, record: Dict[str, Any]) -> None:
        """
        Persist an acceptance record once. If a record with the same acceptance_id
        already exists, raises RuntimeError. No updates allowed.
        """
        aid = record.get("acceptance_id")
        if not aid:
            raise RuntimeError("Acceptance record must have acceptance_id.")
        path = self._path(aid)
        if path.exists():
            raise RuntimeError(
                f"Acceptance records are immutable for governance audit. "
                f"A record with acceptance_id={aid!r} already exists. Any attempt to overwrite is forbidden."
            )
        _validate_acceptance_guardrails(record, self._submission_store)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)

    def get_by_submission(self, submission_id: str) -> List[Dict[str, Any]]:
        """List all acceptance records for that submission, chronological by decided_at."""
        submission_id = (submission_id or "").strip()
        records = []
        for path in self._base.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    rec = json.load(f)
                if (rec.get("submission_id") or "").strip() == submission_id:
                    records.append(rec)
            except (json.JSONDecodeError, KeyError):
                continue
        records.sort(key=lambda r: r.get("decided_at") or "")
        return records

    def list_by_project(self, project_id: str) -> List[Dict[str, Any]]:
        """List all acceptance records for the project, chronological by decided_at."""
        project_id = (project_id or "").strip()
        records = []
        for path in self._base.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    rec = json.load(f)
                if (rec.get("project_id") or "").strip() == project_id:
                    records.append(rec)
            except (json.JSONDecodeError, KeyError):
                continue
        records.sort(key=lambda r: r.get("decided_at") or "")
        return records
