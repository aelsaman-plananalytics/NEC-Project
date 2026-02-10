"""
Unit tests for Submission Evolution Engine.

Proves: first submission, became acceptable, became not acceptable, unchanged,
and that assumptions do not affect evolution (blockers still appear, no false became_aligned).
"""

import pytest

from app.evolution.submission_evolution import build_submission_evolution


def _report_row(ob_id: str, aligned: bool, name: str, required_action: str = None):
    return {
        "id": ob_id,
        "aligned": aligned,
        "mandatory_for_acceptance": True,
        "canonical_name": name,
        "original_contract_text": name,
        "required_action": required_action,
    }


def test_first_submission_previous_none():
    """When previous_response is None, status_change is FIRST_SUBMISSION."""
    current = {
        "acceptability_status": "NOT_ACCEPTABLE",
        "obligations_report": [_report_row("OBL-001", False, "Temporary Works", "Add WBS containing 'temporary works'")],
        "obligations_not_represented_but_mandatory": [
            {"id": "OBL-001", "original_contract_text": "Temporary Works", "required_action": "Add WBS containing 'temporary works'"},
        ],
    }
    out = build_submission_evolution(current, previous_response=None)

    assert out["submission_evolution_summary"]["status_change"] == "FIRST_SUBMISSION"
    assert out["submission_evolution_summary"]["current_acceptability"] == "NOT_ACCEPTABLE"
    assert out["submission_evolution_summary"]["previous_acceptability"] is None
    assert len(out["obligation_changes"]["became_aligned"]) == 0
    assert len(out["obligation_changes"]["became_unaligned"]) == 0
    assert len(out["current_blockers"]) == 1
    assert out["current_blockers"][0]["required_action"] == "Add WBS containing 'temporary works'"


def test_not_acceptable_to_acceptable_one_became_aligned():
    """One mandatory obligation becomes aligned -> status_change BECAME_ACCEPTABLE."""
    previous = {
        "acceptability_status": "NOT_ACCEPTABLE",
        "obligations_report": [_report_row("OBL-001", False, "Temporary Works")],
        "obligations_not_represented_but_mandatory": [{"id": "OBL-001", "original_contract_text": "Temporary Works"}],
    }
    current = {
        "acceptability_status": "ACCEPTABLE",
        "obligations_report": [_report_row("OBL-001", True, "Temporary Works")],
        "obligations_not_represented_but_mandatory": [],
    }
    out = build_submission_evolution(current, previous_response=previous)

    assert out["submission_evolution_summary"]["status_change"] == "BECAME_ACCEPTABLE"
    assert out["submission_evolution_summary"]["current_acceptability"] == "ACCEPTABLE"
    assert out["submission_evolution_summary"]["previous_acceptability"] == "NOT_ACCEPTABLE"
    assert len(out["obligation_changes"]["became_aligned"]) == 1
    assert out["obligation_changes"]["became_aligned"][0]["obligation_id"] == "OBL-001"
    assert len(out["obligation_changes"]["became_unaligned"]) == 0
    assert len(out["current_blockers"]) == 0
    assert "now represented" in out["planner_guidance"]["summary_text"]
    assert "acceptable" in out["planner_guidance"]["summary_text"].lower()


def test_acceptable_to_not_acceptable_became_unaligned():
    """Mandatory obligation becomes unaligned -> status_change BECAME_NOT_ACCEPTABLE."""
    previous = {
        "acceptability_status": "ACCEPTABLE",
        "obligations_report": [_report_row("OBL-001", True, "Temporary Works")],
        "obligations_not_represented_but_mandatory": [],
    }
    current = {
        "acceptability_status": "NOT_ACCEPTABLE",
        "obligations_report": [_report_row("OBL-001", False, "Temporary Works", "Add WBS containing 'temporary works'")],
        "obligations_not_represented_but_mandatory": [
            {"id": "OBL-001", "original_contract_text": "Temporary Works", "required_action": "Add WBS containing 'temporary works'"},
        ],
    }
    out = build_submission_evolution(current, previous_response=previous)

    assert out["submission_evolution_summary"]["status_change"] == "BECAME_NOT_ACCEPTABLE"
    assert out["submission_evolution_summary"]["current_acceptability"] == "NOT_ACCEPTABLE"
    assert out["submission_evolution_summary"]["previous_acceptability"] == "ACCEPTABLE"
    assert len(out["obligation_changes"]["became_aligned"]) == 0
    assert len(out["obligation_changes"]["became_unaligned"]) == 1
    assert out["obligation_changes"]["became_unaligned"][0]["obligation_id"] == "OBL-001"
    assert len(out["current_blockers"]) == 1
    assert "no longer represented" in out["planner_guidance"]["summary_text"] or "not acceptable" in out["planner_guidance"]["summary_text"]


def test_unchanged_alignment_unchanged():
    """Alignment unchanged -> status_change UNCHANGED."""
    prev_report = [_report_row("OBL-001", False, "Temporary Works")]
    curr_report = [_report_row("OBL-001", False, "Temporary Works", "Add WBS containing 'temporary works'")]
    previous = {
        "acceptability_status": "NOT_ACCEPTABLE",
        "obligations_report": prev_report,
        "obligations_not_represented_but_mandatory": [{"id": "OBL-001", "original_contract_text": "Temporary Works"}],
    }
    current = {
        "acceptability_status": "NOT_ACCEPTABLE",
        "obligations_report": curr_report,
        "obligations_not_represented_but_mandatory": [
            {"id": "OBL-001", "original_contract_text": "Temporary Works", "required_action": "Add WBS containing 'temporary works'"},
        ],
    }
    out = build_submission_evolution(current, previous_response=previous)

    assert out["submission_evolution_summary"]["status_change"] == "UNCHANGED"
    assert len(out["obligation_changes"]["became_aligned"]) == 0
    assert len(out["obligation_changes"]["became_unaligned"]) == 0
    assert len(out["current_blockers"]) == 1
    assert "No change" in out["planner_guidance"]["summary_text"] or "remains not acceptable" in out["planner_guidance"]["summary_text"]


def test_assumptions_do_not_affect_evolution_blocker_still_appears():
    """Assumption present in both responses; blocker still appears; no false became_aligned."""
    blocker = {
        "id": "OBL-001",
        "original_contract_text": "Temporary Works",
        "canonical_name": "Temporary Works",
        "required_action": "Add at least one activity under a WBS containing 'temporary works'",
        "explicit_assumption": "covered_by_later_submission",
    }
    previous = {
        "acceptability_status": "NOT_ACCEPTABLE",
        "obligations_report": [_report_row("OBL-001", False, "Temporary Works")],
        "obligations_not_represented_but_mandatory": [blocker],
        "planner_assumptions_used": [{"obligation_id": "OBL-001", "assumption_type": "covered_by_later_submission"}],
    }
    current = {
        "acceptability_status": "NOT_ACCEPTABLE",
        "obligations_report": [_report_row("OBL-001", False, "Temporary Works", blocker["required_action"])],
        "obligations_not_represented_but_mandatory": [blocker],
        "planner_assumptions_used": [{"obligation_id": "OBL-001", "assumption_type": "covered_by_later_submission"}],
    }
    out = build_submission_evolution(current, previous_response=previous)

    # Blocker still appears (assumption does not remove it)
    assert len(out["current_blockers"]) == 1
    assert out["current_blockers"][0]["obligation_id"] == "OBL-001"
    assert out["current_blockers"][0]["required_action"] == blocker["required_action"]

    # No false became_aligned (alignment stayed False)
    assert len(out["obligation_changes"]["became_aligned"]) == 0
    assert len(out["obligation_changes"]["became_unaligned"]) == 0

    assert out["submission_evolution_summary"]["status_change"] == "UNCHANGED"


def test_normalize_not_acceptable_spelling():
    """Validator may return 'NOT ACCEPTABLE'; evolution normalizes to NOT_ACCEPTABLE in output."""
    current = {"acceptability_status": "NOT ACCEPTABLE", "obligations_report": [], "obligations_not_represented_but_mandatory": []}
    out = build_submission_evolution(current, previous_response=None)
    assert out["submission_evolution_summary"]["current_acceptability"] == "NOT_ACCEPTABLE"
