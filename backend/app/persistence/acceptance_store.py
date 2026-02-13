"""
Acceptance record persistence: immutable, write-once.

Acceptance records are immutable for governance audit. Any attempt to overwrite
an existing acceptance_id raises RuntimeError. No updates, no deletes.
Uses storage abstraction (local or other backend).
"""

from pathlib import Path
from typing import Dict, List, Any, Optional, TYPE_CHECKING

from app.governance.acceptance_records import VALID_DECISIONS
from app.persistence.integrity import compute_record_hash
from app.persistence.submission_store import SubmissionStore

if TYPE_CHECKING:
    from app.storage.storage_interface import StorageInterface


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


def _default_storage() -> "StorageInterface":
    from app.storage import get_storage
    return get_storage()


class AcceptanceStore:
    """
    Immutable acceptance store. Write-once per acceptance_id.
    Acceptance records are immutable for governance audit purposes.
    Uses storage abstraction.
    """

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        submission_store: Optional[SubmissionStore] = None,
        storage: Optional["StorageInterface"] = None,
    ):
        self._storage = storage if storage is not None else _default_storage()
        self._prefix = "acceptance_history"
        self._submission_store = submission_store or SubmissionStore()

    def _path(self, acceptance_id: str) -> str:
        safe_id = "".join(c for c in acceptance_id if c.isalnum() or c == "-")
        if not safe_id:
            safe_id = "unknown"
        return f"{self._prefix}/{safe_id}.json"

    def save_acceptance(self, record: Dict[str, Any]) -> None:
        """
        Persist an acceptance record once. If a record with the same acceptance_id
        already exists, raises RuntimeError. No updates allowed.
        """
        aid = record.get("acceptance_id")
        if not aid:
            raise RuntimeError("Acceptance record must have acceptance_id.")
        path = self._path(aid)
        if self._storage.exists(path):
            raise RuntimeError(
                f"Acceptance records are immutable for governance audit. "
                f"A record with acceptance_id={aid!r} already exists. Any attempt to overwrite is forbidden."
            )
        stored_hash = record.get("record_hash")
        if stored_hash is None:
            raise RuntimeError("Acceptance record must include record_hash.")
        computed = compute_record_hash(record)
        if computed != stored_hash:
            raise RuntimeError("Acceptance record integrity violation.")
        _validate_acceptance_guardrails(record, self._submission_store)
        self._storage.save_json(path, record)

    def get_by_submission(self, submission_id: str) -> List[Dict[str, Any]]:
        """List all acceptance records for that submission, chronological by decided_at."""
        submission_id = (submission_id or "").strip()
        records = []
        for rel_path in self._storage.list_paths(self._prefix):
            rec = self._storage.load_json(rel_path)
            if rec is None:
                continue
            if (rec.get("submission_id") or "").strip() != submission_id:
                continue
            if "record_hash" not in rec:
                raise RuntimeError("Stored record missing integrity hash.")
            if compute_record_hash(rec) != rec["record_hash"]:
                raise RuntimeError("Integrity check failed: record modified after save.")
            records.append(rec)
        records.sort(key=lambda r: r.get("decided_at") or "")
        return records

    def list_by_project(self, project_id: str) -> List[Dict[str, Any]]:
        """List all acceptance records for the project, chronological by decided_at."""
        project_id = (project_id or "").strip()
        records = []
        for rel_path in self._storage.list_paths(self._prefix):
            rec = self._storage.load_json(rel_path)
            if rec is None:
                continue
            if (rec.get("project_id") or "").strip() != project_id:
                continue
            if "record_hash" not in rec:
                raise RuntimeError("Stored record missing integrity hash.")
            if compute_record_hash(rec) != rec["record_hash"]:
                raise RuntimeError("Integrity check failed: record modified after save.")
            records.append(rec)
        records.sort(key=lambda r: r.get("decided_at") or "")
        return records
