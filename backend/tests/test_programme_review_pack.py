"""
Tests for Programme Review Pack (Step 4A): read-only presentation layer.

No validator, no inference. Pack is assembled from stored submission and acceptance only.
"""

import pytest

from app.review.programme_review_pack import build_programme_review_pack
from app.persistence.submission_store import SubmissionStore, create_submission_record
from app.persistence.acceptance_store import AcceptanceStore
from app.storage.local_storage import LocalStorage
from app.diagnostics.obligation_diagnostics import build_obligation_diagnostics
from app.evolution.submission_evolution import build_submission_evolution
from app.guidance.planner_guidance import build_planner_guidance


def _submission_record_not_acceptable(
    submission_id: str,
    project_id: str,
    programme_name: str = "Test Programme",
):
    """Stored submission: NOT_ACCEPTABLE with one mandatory blocker (counts reconcile)."""
    vr = {
        "acceptability_status": "NOT_ACCEPTABLE",
        "overall_status": "fail",
        "obligations_report": [
            {
                "id": "OBL-001",
                "aligned": False,
                "mandatory_for_acceptance": True,
                "original_contract_text": "Temporary Works",
                "canonical_name": "Temporary Works",
                "evidence_mode": "WBS_ONLY",
                "canonical_match_string": "temporary works",
                "required_action": "Add WBS containing 'temporary works'",
            },
        ],
        "obligations_not_represented_but_mandatory": [
            {
                "id": "OBL-001",
                "original_contract_text": "Temporary Works",
                "required_action": "Add WBS containing 'temporary works'",
                "evidence_mode": "WBS_ONLY",
                "canonical_match_string": "temporary works",
            },
        ],
    }
    diag = build_obligation_diagnostics(vr)
    evo = build_submission_evolution(vr)
    guidance = build_planner_guidance(vr)
    return create_submission_record(
        project_id=project_id,
        programme_name=programme_name,
        submission_stage="initial",
        validation_response=vr,
        planner_assumptions_used=[],
        diagnostics_output=diag,
        evolution_output=evo,
        planner_guidance_output=guidance,
        submission_id=submission_id,
    )


def _submission_record_acceptable(submission_id: str, project_id: str):
    """Stored submission: ACCEPTABLE, no blockers (counts reconcile)."""
    vr = {
        "acceptability_status": "ACCEPTABLE",
        "overall_status": "pass",
        "obligations_report": [
            {
                "id": "OBL-001",
                "aligned": True,
                "mandatory_for_acceptance": True,
                "original_contract_text": "Temporary Works",
            },
        ],
        "obligations_not_represented_but_mandatory": [],
    }
    diag = build_obligation_diagnostics(vr)
    evo = build_submission_evolution(vr)
    guidance = build_planner_guidance(vr)
    return create_submission_record(
        project_id=project_id,
        programme_name="Test Programme",
        submission_stage="initial",
        validation_response=vr,
        planner_assumptions_used=[],
        diagnostics_output=diag,
        evolution_output=evo,
        planner_guidance_output=guidance,
        submission_id=submission_id,
    )


@pytest.fixture
def tmp_dirs(tmp_path):
    sub_dir = tmp_path / "submissions"
    acc_dir = tmp_path / "acceptance"
    sub_dir.mkdir()
    acc_dir.mkdir()
    return sub_dir, acc_dir


@pytest.fixture
def submission_store(tmp_dirs):
    return SubmissionStore(storage=LocalStorage(tmp_dirs[0]))


@pytest.fixture
def acceptance_store(tmp_dirs, submission_store):
    return AcceptanceStore(storage=LocalStorage(tmp_dirs[1]), submission_store=submission_store)


def test_not_acceptable_submission_with_blockers(
    submission_store,
    acceptance_store,
    request,
):
    """NOT_ACCEPTABLE submission with blockers: review_pack shows NOT_ACCEPTABLE, not_represented populated, governance may be empty."""
    sid = f"sub-not-1-{request.node.name}"
    rec = _submission_record_not_acceptable(sid, "proj-1")
    submission_store.save(rec)

    pack = build_programme_review_pack(sid, submission_store, acceptance_store)

    assert pack["acceptability_section"]["acceptability_status"] == "NOT_ACCEPTABLE"
    assert pack["acceptability_section"]["overall_status"] == "fail"
    assert "Clause 31" in pack["acceptability_section"]["legal_note"]

    mos = pack["mandatory_obligations_status"]
    assert mos["total_mandatory"] == 1
    assert mos["aligned"] == 0
    assert mos["not_aligned"] == 1
    assert len(mos["not_represented"]) == 1
    assert mos["not_represented"][0]["obligation_id"] == "OBL-001"
    assert "temporary works" in (mos["not_represented"][0]["required_action"] or "").lower()
    assert mos["not_represented"][0]["evidence_mode"] == "WBS_ONLY"

    assert pack["governance"]["latest_acceptance_decision"] is None
    assert pack["governance"]["acceptance_history"] == []
    assert "do not alter acceptability" in pack["governance"]["governance_note"].lower()

    assert pack["review_metadata"]["submission_id"] == sid
    assert pack["planner_guidance"] is not None
    assert pack["diagnostics_summary"] is not None
    assert pack["submission_evolution"] is not None


def test_acceptable_submission_with_acceptance_history(
    submission_store,
    acceptance_store,
    request,
):
    """ACCEPTABLE submission with acceptance history: no blockers, latest acceptance surfaced correctly."""
    sid = f"sub-acc-1-{request.node.name}"
    rec = _submission_record_acceptable(sid, "proj-1")
    submission_store.save(rec)

    from app.governance.acceptance_records import create_acceptance_record
    acc = create_acceptance_record(
        submission_id=sid,
        project_id="proj-1",
        decision="ACCEPT",
        decided_by="Supervisor",
    )
    acceptance_store.save_acceptance(acc)

    pack = build_programme_review_pack(sid, submission_store, acceptance_store)

    assert pack["acceptability_section"]["acceptability_status"] == "ACCEPTABLE"
    assert pack["acceptability_section"]["overall_status"] == "pass"
    assert pack["mandatory_obligations_status"]["total_mandatory"] == 1
    assert pack["mandatory_obligations_status"]["aligned"] == 1
    assert pack["mandatory_obligations_status"]["not_aligned"] == 0
    assert len(pack["mandatory_obligations_status"]["not_represented"]) == 0

    assert pack["governance"]["latest_acceptance_decision"] == "ACCEPT"
    assert len(pack["governance"]["acceptance_history"]) == 1
    assert pack["governance"]["acceptance_history"][0]["decided_by"] == "Supervisor"


def test_acceptable_submission_with_not_accept_governance(
    submission_store,
    acceptance_store,
):
    """ACCEPTABLE submission with NOT_ACCEPT governance: acceptability still ACCEPTABLE, governance decision surfaced, no mutation."""
    rec = _submission_record_acceptable("sub-acc-2", "proj-1")
    submission_store.save(rec)

    from app.governance.acceptance_records import create_acceptance_record
    acc = create_acceptance_record(
        submission_id="sub-acc-2",
        project_id="proj-1",
        decision="NOT_ACCEPT",
        decided_by="Client",
    )
    acceptance_store.save_acceptance(acc)

    pack = build_programme_review_pack("sub-acc-2", submission_store, acceptance_store)

    assert pack["acceptability_section"]["acceptability_status"] == "ACCEPTABLE"
    assert pack["governance"]["latest_acceptance_decision"] == "NOT_ACCEPT"
    assert len(pack["mandatory_obligations_status"]["not_represented"]) == 0


def test_guardrail_invalid_persisted_record_missing_planner_guidance(
    acceptance_store,
):
    """Manually construct invalid persisted record (missing planner_guidance_output); ensure RuntimeError."""
    # Mock store returns record missing planner_guidance_output (simulated persistence breach)
    vr = {
        "acceptability_status": "NOT_ACCEPTABLE",
        "overall_status": "fail",
        "obligations_report": [{"id": "OBL-001", "aligned": False, "mandatory_for_acceptance": True}],
        "obligations_not_represented_but_mandatory": [{"id": "OBL-001", "required_action": "Add WBS"}],
    }
    class MockSubmissionStore:
        def get(self, submission_id):
            if submission_id != "sub-bad":
                return None
            return {
                "submission_id": "sub-bad",
                "project_id": "proj-1",
                "programme_name": "P",
                "submission_stage": "initial",
                "created_at": "2025-01-01T00:00:00Z",
                "previous_submission_id": None,
                "validation_response": vr,
                "planner_guidance_output": None,  # missing - persistence breach
                "diagnostics_output": {},
                "evolution_output": {"current_blockers": [], "obligation_changes": {"became_aligned": [], "became_unaligned": []}},
            }
    mock_store = MockSubmissionStore()
    with pytest.raises(RuntimeError) as exc_info:
        build_programme_review_pack("sub-bad", mock_store, acceptance_store)
    assert "planner_guidance" in str(exc_info.value).lower() or "persistence" in str(exc_info.value).lower()


def test_guardrail_acceptable_but_not_represented_non_empty_raises(
    acceptance_store,
):
    """Guardrail: ACCEPTABLE with non-empty not_represented → RuntimeError (contradiction)."""
    # SubmissionStore would reject saving this; use a mock store that returns contradictory data
    # to exercise the review pack's own guard.
    class MockSubmissionStore:
        def get(self, submission_id):
            if submission_id != "sub-contra":
                return None
            vr = {
                "acceptability_status": "ACCEPTABLE",
                "overall_status": "pass",
                "obligations_report": [
                    {"id": "OBL-001", "aligned": True, "mandatory_for_acceptance": True},
                ],
                "obligations_not_represented_but_mandatory": [
                    {"id": "OBL-002", "required_action": "Add WBS", "original_contract_text": "Other"},
                ],
            }
            return {
                "submission_id": "sub-contra",
                "project_id": "proj-1",
                "programme_name": "P",
                "submission_stage": "initial",
                "created_at": "2025-01-01T00:00:00Z",
                "previous_submission_id": None,
                "validation_response": vr,
                "planner_guidance_output": {"planner_guidance": {"current_acceptability": "ACCEPTABLE"}},
                "diagnostics_output": {},
                "evolution_output": {"current_blockers": [], "obligation_changes": {"became_aligned": [], "became_unaligned": []}},
            }
    mock_store = MockSubmissionStore()
    with pytest.raises(RuntimeError) as exc_info:
        build_programme_review_pack("sub-contra", mock_store, acceptance_store)
    assert "ACCEPTABLE" in str(exc_info.value) and "not_represented" in str(exc_info.value).lower()


def test_submission_not_found_raises(submission_store, acceptance_store):
    """Missing submission_id → RuntimeError."""
    with pytest.raises(RuntimeError) as exc_info:
        build_programme_review_pack("nonexistent-id", submission_store, acceptance_store)
    assert "not found" in str(exc_info.value).lower()
