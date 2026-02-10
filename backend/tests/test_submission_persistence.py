"""
Tests for submission persistence (Step 3A): immutability, audit trail, no recomputation.

Proves: v1 NOT_ACCEPTABLE → v2 ACCEPTABLE history; overwrite fails; reload matches stored;
historical acceptability is read-only from stored data.
"""

import pytest

from app.persistence.submission_store import (
    SubmissionStore,
    create_submission_record,
    _validate_guardrails,
)
from app.diagnostics.obligation_diagnostics import build_obligation_diagnostics
from app.evolution.submission_evolution import build_submission_evolution
from app.guidance.planner_guidance import build_planner_guidance


def _not_acceptable_response(blocker_id: str = "OBL-001", name: str = "Temporary Works", required_action: str = "Add WBS containing 'temporary works'"):
    return {
        "acceptability_status": "NOT_ACCEPTABLE",
        "overall_status": "fail",
        "obligations_report": [
            {"id": blocker_id, "aligned": False, "original_contract_text": name, "required_action": required_action},
        ],
        "obligations_not_represented_but_mandatory": [
            {"id": blocker_id, "original_contract_text": name, "required_action": required_action},
        ],
    }


def _acceptable_response(obligation_id: str = "OBL-001", name: str = "Temporary Works"):
    return {
        "acceptability_status": "ACCEPTABLE",
        "overall_status": "pass",
        "obligations_report": [
            {"id": obligation_id, "aligned": True, "original_contract_text": name},
        ],
        "obligations_not_represented_but_mandatory": [],
    }


@pytest.fixture
def store_dir(tmp_path):
    return tmp_path


@pytest.fixture
def store(store_dir):
    return SubmissionStore(store_dir)


def test_two_submissions_v1_not_acceptable_v2_acceptable_history(store: SubmissionStore):
    """v1 NOT_ACCEPTABLE, v2 ACCEPTABLE → history shows correct evolution without recomputation."""
    project_id = "proj-1"
    v1_response = _not_acceptable_response()
    v1_diag = build_obligation_diagnostics(v1_response)
    v1_evolution = build_submission_evolution(v1_response, previous_response=None)
    v1_guidance = build_planner_guidance(v1_response, previous_response=None)

    r1 = create_submission_record(
        project_id=project_id,
        programme_name="Programme A",
        submission_stage="initial",
        validation_response=v1_response,
        planner_assumptions_used=[],
        diagnostics_output=v1_diag,
        evolution_output=v1_evolution,
        planner_guidance_output=v1_guidance,
        previous_submission_id=None,
    )
    store.save(r1)

    v2_response = _acceptable_response()
    v2_diag = build_obligation_diagnostics(v2_response)
    v2_evolution = build_submission_evolution(v2_response, previous_response=v1_response)
    v2_guidance = build_planner_guidance(v2_response, previous_response=v1_response)

    r2 = create_submission_record(
        project_id=project_id,
        programme_name="Programme A",
        submission_stage="interim",
        validation_response=v2_response,
        planner_assumptions_used=[],
        diagnostics_output=v2_diag,
        evolution_output=v2_evolution,
        planner_guidance_output=v2_guidance,
        previous_submission_id=r1["submission_id"],
    )
    store.save(r2)

    history = store.get_submission_history(project_id)
    assert len(history) == 2
    first, second = history[0], history[1]
    assert first["acceptability_status"] == "NOT_ACCEPTABLE"
    assert len(first["blockers"]) == 1
    assert second["acceptability_status"] == "ACCEPTABLE"
    assert len(second["blockers"]) == 0
    assert len(second["resolved_obligations"]) == 1
    assert second["previous_submission_id"] == r1["submission_id"]


def test_attempting_to_overwrite_raises_runtime_error(store: SubmissionStore):
    """Attempting to mutate (overwrite) a stored submission fails."""
    v1 = _not_acceptable_response()
    r1 = create_submission_record(
        project_id="p",
        programme_name="P",
        submission_stage="initial",
        validation_response=v1,
        planner_assumptions_used=[],
        diagnostics_output=build_obligation_diagnostics(v1),
        evolution_output=build_submission_evolution(v1),
        planner_guidance_output=build_planner_guidance(v1),
    )
    store.save(r1)
    with pytest.raises(RuntimeError) as exc_info:
        store.save(r1)
    assert "immutable" in str(exc_info.value).lower() or "overwrite" in str(exc_info.value).lower()


def test_reloaded_diagnostics_guidance_match_stored_exactly(store: SubmissionStore):
    """Reloaded diagnostics and planner_guidance match stored outputs exactly."""
    v1 = _not_acceptable_response()
    diag = build_obligation_diagnostics(v1)
    evolution = build_submission_evolution(v1)
    guidance = build_planner_guidance(v1)
    r1 = create_submission_record(
        project_id="p",
        programme_name="P",
        submission_stage="initial",
        validation_response=v1,
        planner_assumptions_used=[],
        diagnostics_output=diag,
        evolution_output=evolution,
        planner_guidance_output=guidance,
    )
    store.save(r1)
    loaded = store.get(r1["submission_id"])
    assert loaded is not None
    assert loaded["diagnostics_output"] == diag
    assert loaded["planner_guidance_output"] == guidance
    assert loaded["evolution_output"] == evolution


def test_historical_acceptability_from_stored_only(store: SubmissionStore):
    """Historical acceptability is read from stored validation_response only (cannot change if code changes later)."""
    v1 = _not_acceptable_response()
    r1 = create_submission_record(
        project_id="p",
        programme_name="P",
        submission_stage="initial",
        validation_response=v1,
        planner_assumptions_used=[],
        diagnostics_output=build_obligation_diagnostics(v1),
        evolution_output=build_submission_evolution(v1),
        planner_guidance_output=build_planner_guidance(v1),
    )
    store.save(r1)
    loaded = store.get(r1["submission_id"])
    assert loaded["validation_response"]["acceptability_status"] == "NOT_ACCEPTABLE"
    history = store.get_submission_history("p")
    assert len(history) == 1
    assert history[0]["acceptability_status"] == "NOT_ACCEPTABLE"


def test_guardrail_acceptability_mismatch_raises():
    """If stored validation_response.acceptability != planner_guidance.current_acceptability → RuntimeError."""
    record = {
        "validation_response": {"acceptability_status": "ACCEPTABLE"},
        "planner_guidance_output": {
            "planner_guidance": {"current_acceptability": "NOT_ACCEPTABLE", "required_before_next_submission": []},
        },
        "evolution_output": {"current_blockers": [], "obligation_changes": {"became_aligned": [], "became_unaligned": []}},
    }
    with pytest.raises(RuntimeError) as exc_info:
        _validate_guardrails(record)
    assert "acceptability" in str(exc_info.value).lower()


def test_guardrail_acceptable_but_blockers_raises():
    """If acceptability is ACCEPTABLE but blockers stored → RuntimeError."""
    record = {
        "validation_response": {
            "acceptability_status": "ACCEPTABLE",
            "obligations_not_represented_but_mandatory": [{"id": "OBL-001"}],
        },
        "planner_guidance_output": {
            "planner_guidance": {"current_acceptability": "ACCEPTABLE", "required_before_next_submission": []},
        },
        "evolution_output": {"current_blockers": [], "obligation_changes": {"became_aligned": [], "became_unaligned": []}},
    }
    with pytest.raises(RuntimeError) as exc_info:
        _validate_guardrails(record)
    assert "ACCEPTABLE" in str(exc_info.value) and "blocker" in str(exc_info.value).lower()


def test_guardrail_evolution_id_not_in_validation_raises():
    """If evolution_output references obligation ID not in validation_response → RuntimeError."""
    record = {
        "validation_response": {
            "acceptability_status": "NOT_ACCEPTABLE",
            "obligations_report": [{"id": "OBL-001"}],
            "obligations_not_represented_but_mandatory": [],
        },
        "planner_guidance_output": {
            "planner_guidance": {"current_acceptability": "NOT_ACCEPTABLE", "required_before_next_submission": []},
        },
        "evolution_output": {
            "current_blockers": [{"obligation_id": "OBL-999", "obligation_name": "Other"}],
            "obligation_changes": {"became_aligned": [], "became_unaligned": []},
        },
    }
    with pytest.raises(RuntimeError) as exc_info:
        _validate_guardrails(record)
    assert "evolution" in str(exc_info.value).lower() or "OBL-999" in str(exc_info.value)
