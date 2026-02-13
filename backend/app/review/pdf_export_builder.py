"""
PDF Export input assembler: Programme Review Pack → PDF export contract only.

Input = Programme Review Pack only. Output = dict matching PDF export contract.
This module is presentation-only. Any logic here is a defect.
No transformation except formatting dates and ordering lists; no conditionals that affect meaning.
"""

from typing import Dict, List, Any

from app.review.pdf_export_contract import (
    REVIEW_PACK_REQUIRED_KEYS,
    LEGAL_ACCEPTABILITY_NOTE,
    GOVERNANCE_NOTE,
    NOT_REPRESENTED_TABLE_FIELDS,
)


def build_pdf_export_input(review_pack: dict) -> dict:
    """
    Build PDF export input from a Programme Review Pack only.
    Output matches the PDF export contract; no new fields. Raises RuntimeError if
    input is not a valid review pack or if guardrails fail.
    """
    if not isinstance(review_pack, dict):
        raise RuntimeError(
            "PDF export input must be built from a Programme Review Pack. "
            "Got non-dict input."
        )
    missing = REVIEW_PACK_REQUIRED_KEYS - set(review_pack.keys())
    if missing:
        raise RuntimeError(
            "PDF export input must be built from a Programme Review Pack. "
            f"Missing required keys: {sorted(missing)}."
        )

    meta = review_pack.get("review_metadata") or {}
    acc = review_pack.get("acceptability_section") or {}
    mos = review_pack.get("mandatory_obligations_status") or {}
    planner = review_pack.get("planner_guidance") or {}
    planner_inner = planner.get("planner_guidance") if isinstance(planner.get("planner_guidance"), dict) else {}
    evolution = review_pack.get("submission_evolution") or {}
    obligation_changes = evolution.get("obligation_changes") or {}
    diagnostics = review_pack.get("diagnostics_summary") or {}
    gov = review_pack.get("governance") or {}

    acceptability_status = (acc.get("acceptability_status") or "").strip()
    not_represented = list(mos.get("not_represented") or [])
    total_mandatory = int(mos.get("total_mandatory") or 0)
    aligned = int(mos.get("aligned") or 0)
    not_aligned = int(mos.get("not_aligned") or 0)

    # Guard: ACCEPTABLE and not_represented non-empty
    if acceptability_status == "ACCEPTABLE" and not_represented:
        raise RuntimeError(
            "PDF export guard: acceptability_status is ACCEPTABLE but not_represented is non-empty. "
            "PDF cannot contradict acceptability."
        )

    # Guard: required_action missing for any not_represented obligation
    for i, row in enumerate(not_represented):
        ra = row.get("required_action")
        if ra is None or (isinstance(ra, str) and not ra.strip()):
            raise RuntimeError(
                f"PDF export guard: required_action is missing for not_represented obligation at index {i}. "
                "Every not_represented row must have required_action."
            )

    # Guard: counts must reconcile
    if aligned + not_aligned != total_mandatory:
        raise RuntimeError(
            "PDF export guard: mandatory obligation counts do not reconcile. "
            f"aligned={aligned}, not_aligned={not_aligned}, total_mandatory={total_mandatory}. "
            "aligned + not_aligned must equal total_mandatory."
        )

    # Not-represented table: verbatim fields only (obligation_name, evidence_mode, canonical_match_string, required_action)
    not_represented_table: List[Dict[str, Any]] = []
    for row in not_represented:
        not_represented_table.append({
            "obligation_name": row.get("obligation_name"),
            "evidence_mode": row.get("evidence_mode"),
            "canonical_match_string": row.get("canonical_match_string"),
            "required_action": row.get("required_action"),
        })

    since_last = planner_inner.get("since_last_submission") or {}
    required_before = list(planner_inner.get("required_before_next_submission") or [])
    resolved = list(since_last.get("resolved_obligations") or [])
    unchanged_blockers = list(since_last.get("unchanged_blockers") or [])
    advisory_notes = list(planner_inner.get("advisory_notes") or [])

    submission_evolution_summary = evolution.get("submission_evolution_summary") or {}
    status_change = (submission_evolution_summary.get("status_change") or "").strip()
    became_aligned = list(obligation_changes.get("became_aligned") or [])
    became_unaligned = list(obligation_changes.get("became_unaligned") or [])

    failure_table = list(diagnostics.get("failure_table") or [])
    diagnostics_summary_text = (diagnostics.get("diagnostics_summary") or "").strip()

    acceptance_history = list(gov.get("acceptance_history") or [])

    # Build output in contract section order; no new fields
    return {
        "cover": {
            "project_id": meta.get("project_id"),
            "programme_name": meta.get("programme_name"),
            "submission_stage": meta.get("submission_stage"),
            "submission_id": meta.get("submission_id"),
            "created_at": meta.get("created_at"),
            "previous_submission_id": meta.get("previous_submission_id"),
        },
        "legal_acceptability": {
            "acceptability_status": acceptability_status,
            "overall_status": (acc.get("overall_status") or "").strip(),
            "legal_note": LEGAL_ACCEPTABILITY_NOTE,
        },
        "mandatory_obligations_status": {
            "total_mandatory": total_mandatory,
            "aligned_count": aligned,
            "not_aligned_count": not_aligned,
            "not_represented": not_represented_table,
        },
        "planner_guidance": {
            "required_before_next_submission": required_before,
            "resolved_obligations": resolved,
            "unchanged_blockers": unchanged_blockers,
            "advisory_notes": advisory_notes,
        },
        "submission_evolution": {
            "status_change": status_change,
            "became_aligned": became_aligned,
            "became_unaligned": became_unaligned,
        },
        "diagnostics_summary": {
            "diagnostics_summary": diagnostics_summary_text,
            "failure_table": failure_table,
        },
        "governance": {
            "latest_acceptance_decision": gov.get("latest_acceptance_decision"),
            "latest_acceptance_comments": gov.get("latest_acceptance_comments"),
            "acceptance_history": acceptance_history,
            "governance_note": GOVERNANCE_NOTE,
        },
    }
