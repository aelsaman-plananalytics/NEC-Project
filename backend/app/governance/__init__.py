"""
Programme acceptance & governance layer.

Acceptance is a human/governance decision; it does not alter acceptability.
"""

from app.governance.acceptance_records import (
    AcceptanceDecision,
    create_acceptance_record,
)
from app.governance.acceptance_summary import build_acceptance_summary

__all__ = [
    "AcceptanceDecision",
    "create_acceptance_record",
    "build_acceptance_summary",
]
