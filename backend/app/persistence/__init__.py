"""
Immutable persistence for validation submissions (NEC audit trail).

Submission records are write-once. No updates. No recomputation on load.
"""

from app.persistence.submission_store import SubmissionStore, create_submission_record

__all__ = ["SubmissionStore", "create_submission_record"]
