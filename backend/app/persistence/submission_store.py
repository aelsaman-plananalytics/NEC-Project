"""
Submission persistence: immutable, write-once records for NEC audit.

Submission records are immutable for NEC audit purposes.
Any attempt to overwrite an existing submission raises RuntimeError.
Only new submissions may reference previous_submission_id.
Ledger-style hash chaining: previous_record_hash links to previous submission's record_hash.
No re-validation or recomputation on load.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from datetime import datetime, timezone

from app.persistence.integrity import compute_record_hash

if TYPE_CHECKING:
    from app.storage.storage_interface import StorageInterface

_ACCEPTABILITY = "acceptability_status"
_OBL_REPORT = "obligations_report"
_NOT_REP_MANDATORY = "obligations_not_represented_but_mandatory"


def _normalize_acceptability(status: Optional[str]) -> str:
    if not status or not str(status).strip():
        return "NOT_ACCEPTABLE"
    s = str(status).strip()
    if s == "NOT ACCEPTABLE":
        return "NOT_ACCEPTABLE"
    if s in ("NOT_ACCEPTABLE", "ACCEPTABLE"):
        return s
    return "NOT_ACCEPTABLE"


def _validation_obligation_ids(validation_response: Dict[str, Any]) -> set:
    """Set of obligation IDs present in validation_response (report + not_represented_but_mandatory)."""
    ids = set()
    for r in (validation_response.get(_OBL_REPORT) or []):
        oid = r.get("id")
        if oid:
            ids.add(oid)
    for r in (validation_response.get(_NOT_REP_MANDATORY) or []):
        oid = r.get("id")
        if oid:
            ids.add(oid)
    return ids


def _evolution_obligation_ids(evolution_output: Dict[str, Any]) -> set:
    """Set of obligation IDs referenced in evolution_output."""
    ids = set()
    for ob in (evolution_output.get("obligation_changes") or {}).get("became_aligned") or []:
        oid = ob.get("obligation_id")
        if oid:
            ids.add(oid)
    for ob in (evolution_output.get("obligation_changes") or {}).get("became_unaligned") or []:
        oid = ob.get("obligation_id")
        if oid:
            ids.add(oid)
    for ob in (evolution_output.get("current_blockers") or []):
        oid = ob.get("obligation_id")
        if oid:
            ids.add(oid)
    return ids


def _validate_guardrails(record: Dict[str, Any]) -> None:
    """
    Hard guards to protect audit authority. Raises RuntimeError if inconsistent.
    """
    vr = record.get("validation_response") or {}
    pg_out = record.get("planner_guidance_output") or {}
    pg = pg_out.get("planner_guidance") or {}
    ev_out = record.get("evolution_output") or {}

    # Guard: stored validation_response.acceptability_status must match stored planner_guidance.current_acceptability
    api_acceptability = _normalize_acceptability(vr.get(_ACCEPTABILITY))
    guidance_acceptability = (pg.get("current_acceptability") or "").strip()
    if api_acceptability != guidance_acceptability:
        raise RuntimeError(
            "Submission guard: validation_response.acceptability_status must match planner_guidance.current_acceptability. "
            f"Got {api_acceptability!r} vs {guidance_acceptability!r}. Stored results are evidence; mismatch indicates corruption."
        )

    # Guard: if ACCEPTABLE, no blockers may be stored
    if api_acceptability == "ACCEPTABLE":
        not_rep = vr.get(_NOT_REP_MANDATORY) or []
        required_before = pg.get("required_before_next_submission") or []
        if not_rep or required_before:
            raise RuntimeError(
                "Submission guard: acceptability is ACCEPTABLE but blockers exist in validation_response or planner_guidance. "
                f"not_represented_but_mandatory count={len(not_rep)}, required_before_next_submission count={len(required_before)}. "
                "Acceptability authority is single source; contradiction is not allowed."
            )

    # Guard: every obligation ID in evolution_output must exist in validation_response
    val_ids = _validation_obligation_ids(vr)
    ev_ids = _evolution_obligation_ids(ev_out)
    missing = ev_ids - val_ids
    if missing:
        raise RuntimeError(
            "Submission guard: evolution_output references obligation IDs not present in validation_response. "
            f"Missing IDs: {missing}. Historical comparison must use stored data only; no external references."
        )


def create_submission_record(
    project_id: str,
    programme_name: str,
    submission_stage: str,
    validation_response: Dict[str, Any],
    planner_assumptions_used: List[Dict[str, Any]],
    diagnostics_output: Dict[str, Any],
    evolution_output: Dict[str, Any],
    planner_guidance_output: Dict[str, Any],
    previous_submission_id: Optional[str] = None,
    submission_id: Optional[str] = None,
    submission_store: Optional["SubmissionStore"] = None,
) -> Dict[str, Any]:
    """
    Build a submission record (does not persist). Caller must pass exact outputs
    from validation API and from build_obligation_diagnostics, build_submission_evolution,
    build_planner_guidance. created_at is set to UTC now.
    When previous_submission_id is set, pass submission_store so previous_record_hash
    can be set for ledger chaining.
    """
    sid = submission_id or str(uuid.uuid4())
    prev_id = previous_submission_id.strip() if previous_submission_id and str(previous_submission_id).strip() else None
    previous_record_hash: Optional[str] = None
    if prev_id:
        if submission_store is None:
            raise RuntimeError("submission_store required when previous_submission_id is set for ledger chaining.")
        previous_record = submission_store.get(prev_id)
        if previous_record is None:
            raise RuntimeError("Ledger chain broken: previous submission not found.")
        previous_record_hash = previous_record["record_hash"]
    record = {
        "submission_id": sid,
        "project_id": (project_id or "").strip(),
        "programme_name": (programme_name or "").strip(),
        "submission_stage": (submission_stage or "initial").strip().lower(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "previous_submission_id": prev_id,
        "previous_record_hash": previous_record_hash,
        "validation_response": validation_response,
        "planner_assumptions_used": list(planner_assumptions_used) if planner_assumptions_used else [],
        "diagnostics_output": diagnostics_output,
        "evolution_output": evolution_output,
        "planner_guidance_output": planner_guidance_output,
    }
    _validate_guardrails(record)
    record["record_hash"] = compute_record_hash(record)
    return record


def _default_storage() -> "StorageInterface":
    from app.storage import get_storage
    return get_storage()


class SubmissionStore:
    """
    Immutable submission store. Write-once per submission_id.
    Submission records are immutable for NEC audit purposes.
    Uses storage abstraction (local or other backend).
    """

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        storage: Optional["StorageInterface"] = None,
    ):
        self._storage = storage if storage is not None else _default_storage()
        self._prefix = "submission_history"

    def _path(self, submission_id: str) -> str:
        safe_id = "".join(c for c in submission_id if c.isalnum() or c == "-")
        if not safe_id:
            safe_id = str(uuid.uuid4())
        return f"{self._prefix}/{safe_id}.json"

    def save(self, record: Dict[str, Any]) -> None:
        """
        Persist a submission record once. If a record with the same submission_id
        already exists, raises RuntimeError. No updates allowed.
        """
        sid = record.get("submission_id")
        if not sid:
            raise RuntimeError("Submission record must have submission_id.")
        path = self._path(sid)
        if self._storage.exists(path):
            raise RuntimeError(
                f"Submission records are immutable for NEC audit purposes. "
                f"A record with submission_id={sid!r} already exists. Any attempt to overwrite is forbidden."
            )
        stored_hash = record.get("record_hash")
        if stored_hash is None:
            raise RuntimeError("Submission record must include record_hash.")
        computed = compute_record_hash(record)
        if computed != stored_hash:
            raise RuntimeError("Submission record integrity violation.")
        _validate_guardrails(record)
        self._storage.save_json(path, record)

    def _verify_chain(self, record: Dict[str, Any]) -> None:
        """Verify ledger chain: previous_record_hash matches previous submission's record_hash. Raises on failure."""
        prev_hash = record.get("previous_record_hash")
        if prev_hash is None:
            return
        prev_id = record.get("previous_submission_id")
        if not prev_id:
            return
        previous_record = self.get(prev_id)
        if previous_record is None:
            raise RuntimeError("Ledger chain broken: previous submission not found.")
        if prev_hash != previous_record["record_hash"]:
            raise RuntimeError("Ledger chain integrity violation: previous record hash mismatch.")

    def get(self, submission_id: str) -> Optional[Dict[str, Any]]:
        """Load a submission by id. Validates guardrails and ledger chain on load. Returns None if not found."""
        path = self._path(submission_id)
        record = self._storage.load_json(path)
        if record is None:
            return None
        if "record_hash" not in record:
            raise RuntimeError("Stored record missing integrity hash.")
        computed = compute_record_hash(record)
        if computed != record["record_hash"]:
            raise RuntimeError("Integrity check failed: record modified after save.")
        _validate_guardrails(record)
        self._verify_chain(record)
        return record

    def list_by_project(self, project_id: str) -> List[Dict[str, Any]]:
        """
        List all submissions for a project in chronological order (created_at).
        Returns full records; validates guardrails on each load. No re-validation of content.
        """
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
            _validate_guardrails(rec)
            self._verify_chain(rec)
            records.append(rec)
        records.sort(key=lambda r: r.get("created_at") or "")
        return records

    def get_submission_history(self, project_id: str) -> List[Dict[str, Any]]:
        """
        Read-only retrieval: list submissions for a project with acceptability_status,
        blockers, and resolved/new blockers from stored evolution_output only.
        No re-validation allowed.
        """
        records = self.list_by_project(project_id)
        out = []
        for rec in records:
            vr = rec.get("validation_response") or {}
            ev = rec.get("evolution_output") or {}
            pg = (rec.get("planner_guidance_output") or {}).get("planner_guidance") or {}
            out.append({
                "submission_id": rec.get("submission_id"),
                "project_id": rec.get("project_id"),
                "programme_name": rec.get("programme_name"),
                "submission_stage": rec.get("submission_stage"),
                "created_at": rec.get("created_at"),
                "previous_submission_id": rec.get("previous_submission_id"),
                "acceptability_status": _normalize_acceptability(vr.get(_ACCEPTABILITY)),
                "blockers": list(ev.get("current_blockers") or []),
                "resolved_obligations": (ev.get("obligation_changes") or {}).get("became_aligned") or [],
                "new_blockers": [],  # derived from evolution: current_blockers that were not in previous
            })
            # new_blockers: compare with previous submission
            prev_id = rec.get("previous_submission_id")
            if prev_id:
                prev_rec = self.get(prev_id)
                if prev_rec:
                    prev_ev = prev_rec.get("evolution_output") or {}
                    prev_blocker_ids = {b.get("obligation_id") for b in (prev_ev.get("current_blockers") or []) if b.get("obligation_id")}
                    current_blockers = list(ev.get("current_blockers") or [])
                    for b in current_blockers:
                        if b.get("obligation_id") not in prev_blocker_ids:
                            out[-1]["new_blockers"].append(b)
        return out
