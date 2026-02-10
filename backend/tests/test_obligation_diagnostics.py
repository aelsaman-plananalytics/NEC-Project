"""
Unit tests for obligation diagnostics (read-only UX truth layer).

Proves:
- ACCEPTABLE responses produce empty failure_table and planner_checklist.
- NOT_ACCEPTABLE responses list all mandatory unaligned obligations.
- Assumptions do not remove checklist items.
- submission_diff shows aligned/unaligned transitions only.
"""

import pytest

from app.diagnostics.obligation_diagnostics import build_obligation_diagnostics


def _acceptable_response():
    """Minimal API-shaped response: ACCEPTABLE, no mandatory unaligned."""
    return {
        "acceptability_status": "ACCEPTABLE",
        "overall_status": "pass",
        "obligations_report": [
            {"id": "OBL-001", "aligned": True, "original_contract_text": "Temporary Works", "required_action": None},
        ],
        "obligations_not_represented_but_mandatory": [],
        "obligation_readiness": [{"obligation_id": "OBL-001", "required_now": True, "aligned": True, "required_action": None}],
        "planner_assumptions_used": [],
        "submission_stage": "initial",
    }


def _not_acceptable_response(obligations_not_represented: list):
    """API-shaped response with given obligations_not_represented_but_mandatory."""
    return {
        "acceptability_status": "NOT_ACCEPTABLE",
        "overall_status": "fail",
        "obligations_report": [
            {"id": "OBL-001", "aligned": False, "original_contract_text": "Temporary Works", "evidence_mode": "WBS_ONLY", "canonical_match_string": "temporary works", "required_action": "Add at least one activity under a WBS or activity name containing 'temporary works'"},
            {"id": "OBL-002", "aligned": True, "original_contract_text": "Design", "required_action": None},
        ],
        "obligations_not_represented_but_mandatory": obligations_not_represented,
        "obligation_readiness": [],
        "planner_assumptions_used": [],
        "submission_stage": "initial",
    }


def test_acceptable_produces_empty_failure_table_and_checklist():
    """ACCEPTABLE responses produce empty failure_table and planner_checklist."""
    resp = _acceptable_response()
    out = build_obligation_diagnostics(resp)
    assert out["diagnostics_summary"] == "Acceptable. All mandatory obligations are represented."
    assert out["failure_table"] == []
    assert out["planner_checklist"] == []
    assert out["acceptability_status"] == "ACCEPTABLE"


def test_not_acceptable_lists_all_mandatory_unaligned():
    """NOT_ACCEPTABLE responses list all mandatory unaligned obligations in failure_table and checklist."""
    not_rep = [
        {
            "id": "OBL-001",
            "original_contract_text": "Temporary Works",
            "canonical_name": "Temporary Works",
            "evidence_mode": "WBS_ONLY",
            "canonical_match_string": "temporary works",
            "required_action": "Add at least one activity under a WBS or activity name containing 'temporary works'",
            "explicit_assumption": None,
        },
    ]
    resp = _not_acceptable_response(not_rep)
    out = build_obligation_diagnostics(resp)

    assert "Not acceptable" in out["diagnostics_summary"]
    assert "1 mandatory" in out["diagnostics_summary"]
    assert len(out["failure_table"]) == 1
    assert out["failure_table"][0]["obligation_id"] == "OBL-001"
    assert out["failure_table"][0]["evidence_mode"] == "WBS_ONLY"
    assert out["failure_table"][0]["canonical_match_string"] == "temporary works"
    assert "temporary works" in (out["failure_table"][0]["required_action"] or "")

    assert len(out["planner_checklist"]) == 1
    assert out["planner_checklist"][0]["obligation_id"] == "OBL-001"
    assert out["planner_checklist"][0]["required_action"] == not_rep[0]["required_action"]


def test_assumptions_do_not_remove_checklist_items():
    """Planner assumptions are shown but do not remove items from failure_table or planner_checklist."""
    not_rep = [
        {
            "id": "OBL-001",
            "original_contract_text": "Temporary Works",
            "evidence_mode": "WBS_ONLY",
            "canonical_match_string": "temporary works",
            "required_action": "Add WBS or activity containing 'temporary works'",
            "explicit_assumption": "covered_by_later_submission",
        },
    ]
    resp = _not_acceptable_response(not_rep)
    resp["planner_assumptions_used"] = [
        {"obligation_id": "OBL-001", "assumption_type": "covered_by_later_submission"},
    ]
    out = build_obligation_diagnostics(resp)

    # Blockers still present
    assert len(out["failure_table"]) == 1
    assert len(out["planner_checklist"]) == 1
    assert out["failure_table"][0]["explicit_assumption"] == "covered_by_later_submission"
    assert out["failure_table"][0]["explicit_assumption_note"] is not None
    assert "does not affect acceptability" in (out["failure_table"][0]["explicit_assumption_note"] or "")

    assert "do not affect acceptability" in out["planner_assumptions_note"]["note"]


def test_submission_diff_shows_aligned_unaligned_transitions_only():
    """submission_diff shows only became_aligned and became_unaligned from obligations_report.aligned."""
    current = {
        "acceptability_status": "NOT_ACCEPTABLE",
        "obligations_report": [
            {"id": "OBL-001", "aligned": True, "original_contract_text": "Temporary Works"},
            {"id": "OBL-002", "aligned": False, "original_contract_text": "Utilities"},
        ],
        "obligations_not_represented_but_mandatory": [
            {"id": "OBL-002", "original_contract_text": "Utilities"},
        ],
    }
    previous = {
        "obligations_report": [
            {"id": "OBL-001", "aligned": False, "original_contract_text": "Temporary Works"},
            {"id": "OBL-002", "aligned": True, "original_contract_text": "Utilities"},
        ],
    }
    out = build_obligation_diagnostics(current, previous_response=previous)

    assert out["submission_diff"] is not None
    became_aligned = out["submission_diff"]["became_aligned"]
    became_unaligned = out["submission_diff"]["became_unaligned"]

    assert len(became_aligned) == 1
    assert became_aligned[0]["id"] == "OBL-001"
    assert became_aligned[0]["original_contract_text"] == "Temporary Works"

    assert len(became_unaligned) == 1
    assert became_unaligned[0]["id"] == "OBL-002"
    assert became_unaligned[0]["original_contract_text"] == "Utilities"


def test_submission_diff_optional_when_no_previous():
    """When previous_response is not provided, submission_diff is None."""
    out = build_obligation_diagnostics(_not_acceptable_response([{"id": "OBL-001"}]))
    assert out.get("submission_diff") is None


def test_empty_response_handled():
    """Empty or minimal response does not raise."""
    out = build_obligation_diagnostics({})
    assert "diagnostics_summary" in out
    assert out["failure_table"] == []
    assert out["planner_checklist"] == []
