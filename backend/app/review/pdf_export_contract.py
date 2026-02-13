"""
PDF Export Contract: authoritative schema for Programme Review Pack → PDF input.

Sections and fields are declared in exact order. No logic, no inference.
This module is presentation-only. Any logic here is a defect.
"""

from typing import List, Dict, Any

# Required top-level keys that identify a valid Programme Review Pack (builder input).
REVIEW_PACK_REQUIRED_KEYS = frozenset({
    "review_metadata",
    "acceptability_section",
    "mandatory_obligations_status",
    "planner_guidance",
    "submission_evolution",
    "diagnostics_summary",
    "governance",
})

# PDF export sections, in this exact order. Output of build_pdf_export_input must follow this.
PDF_EXPORT_SECTION_ORDER: List[str] = [
    "cover",
    "legal_acceptability",
    "mandatory_obligations_status",
    "planner_guidance",
    "submission_evolution",
    "diagnostics_summary",
    "governance",
]

# Fixed text for PDF (verbatim; no edits).
LEGAL_ACCEPTABILITY_NOTE = (
    "Acceptability is determined under NEC Clause 31 and is independent of governance decisions."
)
GOVERNANCE_NOTE = (
    "Governance decisions do not alter programme acceptability."
)

# Cover field names (from review_metadata).
COVER_FIELDS = [
    "project_id",
    "programme_name",
    "submission_stage",
    "submission_id",
    "created_at",
    "previous_submission_id",
]

# Not-represented table column names for PDF.
NOT_REPRESENTED_TABLE_FIELDS = [
    "obligation_name",
    "evidence_mode",
    "canonical_match_string",
    "required_action",
]
