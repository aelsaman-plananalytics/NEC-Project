"""
Unit tests for Planner Guidance (Step 2B).

Proves: first submission NOT ACCEPTABLE, NOT_ACCEPTABLE→ACCEPTABLE, blocker persists,
assumptions do not remove blockers, and acceptable state invariant.
"""

import pytest

from app.guidance.planner_guidance import build_planner_guidance


def _report_row(ob_id: str, aligned: bool, name: str, required_action: str = None, evidence_mode: str = None, canonical_match_string: str = None):
    r = {
        "id": ob_id,
        "aligned": aligned,
        "mandatory_for_acceptance": True,
        "canonical_name": name,
        "original_contract_text": name,
        "required_action": required_action,
    }
    if evidence_mode is not None:
        r["evidence_mode"] = evidence_mode
    if canonical_match_string is not None:
        r["canonical_match_string"] = canonical_match_string
    return r


def _blocker(ob_id: str, name: str, required_action: str, evidence_mode: str = "WBS_ONLY", canonical_match_string: str = "temporary works"):
    return {
        "id": ob_id,
        "original_contract_text": name,
        "canonical_name": name,
        "required_action": required_action,
        "evidence_mode": evidence_mode,
        "canonical_match_string": canonical_match_string,
    }


def test_first_submission_not_acceptable_all_blockers_in_required():
    """First submission, NOT ACCEPTABLE: all blockers in required_before_next_submission, resolved_obligations empty."""
    blocker = _blocker("OBL-001", "Temporary Works", "Add at least one activity under a WBS containing 'temporary works'")
    current = {
        "acceptability_status": "NOT_ACCEPTABLE",
        "submission_stage": "initial",
        "obligations_report": [_report_row("OBL-001", False, "Temporary Works", blocker["required_action"], "WBS_ONLY", "temporary works")],
        "obligations_not_represented_but_mandatory": [blocker],
    }
    out = build_planner_guidance(current, previous_response=None)

    pg = out["planner_guidance"]
    assert pg["current_acceptability"] == "NOT_ACCEPTABLE"
    assert pg["status_change"] == "FIRST_SUBMISSION"
    assert pg["submission_stage"] == "initial"
    assert len(pg["since_last_submission"]["resolved_obligations"]) == 0
    assert len(pg["required_before_next_submission"]) == 1
    assert pg["required_before_next_submission"][0]["obligation_id"] == "OBL-001"
    assert pg["required_before_next_submission"][0]["required_action"] == blocker["required_action"]
    assert pg["required_before_next_submission"][0]["evidence_mode"] == "WBS_ONLY"
    assert pg["required_before_next_submission"][0]["canonical_match_string"] == "temporary works"
    assert len(pg["advisory_notes"]) >= 2


def test_not_acceptable_to_acceptable_required_empty_resolved_populated():
    """NOT_ACCEPTABLE → ACCEPTABLE: required_before_next_submission empty, resolved_obligations populated, status BECAME_ACCEPTABLE."""
    previous = {
        "acceptability_status": "NOT_ACCEPTABLE",
        "obligations_report": [_report_row("OBL-001", False, "Temporary Works")],
        "obligations_not_represented_but_mandatory": [_blocker("OBL-001", "Temporary Works", "Add WBS containing 'temporary works'")],
    }
    current = {
        "acceptability_status": "ACCEPTABLE",
        "obligations_report": [_report_row("OBL-001", True, "Temporary Works")],
        "obligations_not_represented_but_mandatory": [],
    }
    out = build_planner_guidance(current, previous_response=previous)

    pg = out["planner_guidance"]
    assert pg["current_acceptability"] == "ACCEPTABLE"
    assert pg["status_change"] == "BECAME_ACCEPTABLE"
    assert len(pg["required_before_next_submission"]) == 0
    assert len(pg["since_last_submission"]["resolved_obligations"]) == 1
    assert pg["since_last_submission"]["resolved_obligations"][0]["obligation_id"] == "OBL-001"


def test_blocker_persists_unchanged_blockers_and_required():
    """Blocker present in both submissions appears in unchanged_blockers and in required_before_next_submission."""
    blocker = _blocker("OBL-001", "Temporary Works", "Add WBS containing 'temporary works'")
    previous = {
        "acceptability_status": "NOT_ACCEPTABLE",
        "obligations_report": [_report_row("OBL-001", False, "Temporary Works", blocker["required_action"])],
        "obligations_not_represented_but_mandatory": [blocker],
    }
    current = {
        "acceptability_status": "NOT_ACCEPTABLE",
        "obligations_report": [_report_row("OBL-001", False, "Temporary Works", blocker["required_action"], "WBS_ONLY", "temporary works")],
        "obligations_not_represented_but_mandatory": [blocker],
    }
    out = build_planner_guidance(current, previous_response=previous)

    pg = out["planner_guidance"]
    assert len(pg["since_last_submission"]["unchanged_blockers"]) == 1
    assert pg["since_last_submission"]["unchanged_blockers"][0]["obligation_id"] == "OBL-001"
    assert len(pg["since_last_submission"]["new_blockers"]) == 0
    assert len(pg["required_before_next_submission"]) == 1
    assert pg["required_before_next_submission"][0]["obligation_id"] == "OBL-001"


def test_planner_assumptions_do_not_remove_blockers():
    """Planner assumptions present: blockers still appear; assumptions only reflected in advisory notes."""
    blocker = _blocker("OBL-001", "Temporary Works", "Add WBS containing 'temporary works'")
    current = {
        "acceptability_status": "NOT_ACCEPTABLE",
        "obligations_report": [_report_row("OBL-001", False, "Temporary Works", blocker["required_action"])],
        "obligations_not_represented_but_mandatory": [blocker],
        "planner_assumptions_used": [{"obligation_id": "OBL-001", "assumption_type": "covered_by_later_submission"}],
    }
    out = build_planner_guidance(current, previous_response=None)

    pg = out["planner_guidance"]
    assert len(pg["required_before_next_submission"]) == 1
    assert "Planner assumptions" in pg["advisory_notes"][0]


def test_acceptable_state_invariant_required_empty_no_blockers():
    """If current_acceptability == ACCEPTABLE then required_before_next_submission empty and no blockers in since_last."""
    current = {
        "acceptability_status": "ACCEPTABLE",
        "obligations_report": [_report_row("OBL-001", True, "Temporary Works")],
        "obligations_not_represented_but_mandatory": [],
    }
    out = build_planner_guidance(current, previous_response=None)

    pg = out["planner_guidance"]
    assert pg["current_acceptability"] == "ACCEPTABLE"
    assert len(pg["required_before_next_submission"]) == 0
    assert len(pg["since_last_submission"]["new_blockers"]) == 0
    assert len(pg["since_last_submission"]["unchanged_blockers"]) == 0


def test_runtime_error_if_acceptable_but_blockers_exist():
    """Safety: RuntimeError if API says ACCEPTABLE but obligations_not_represented_but_mandatory is non-empty."""
    current = {
        "acceptability_status": "ACCEPTABLE",
        "obligations_report": [_report_row("OBL-001", True, "Temporary Works")],
        "obligations_not_represented_but_mandatory": [
            _blocker("OBL-001", "Temporary Works", "Add WBS"),
        ],
    }
    with pytest.raises(RuntimeError) as exc_info:
        build_planner_guidance(current, previous_response=None)
    assert "ACCEPTABLE" in str(exc_info.value) and "blockers" in str(exc_info.value).lower()


def test_runtime_error_if_blocker_missing_required_action():
    """Safety: RuntimeError if a blocker has no required_action."""
    current = {
        "acceptability_status": "NOT_ACCEPTABLE",
        "obligations_report": [_report_row("OBL-001", False, "Temporary Works")],
        "obligations_not_represented_but_mandatory": [
            {"id": "OBL-001", "original_contract_text": "Temporary Works", "required_action": None},
        ],
    }
    with pytest.raises(RuntimeError) as exc_info:
        build_planner_guidance(current, previous_response=None)
    assert "required_action" in str(exc_info.value)
