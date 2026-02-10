"""
Submission evolution: tracks programme changes across submissions (Clause 31).

Read-only. Does not re-run validation or change acceptability.
"""

from app.evolution.submission_evolution import build_submission_evolution

__all__ = ["build_submission_evolution"]
