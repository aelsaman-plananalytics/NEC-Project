"""
Tests for acceptance & governance layer (Step 3B).

Acceptance does not change acceptability. Tests do not import or run the validator.
"""

import pytest

from app.governance.acceptance_records import create_acceptance_record
from app.governance.acceptance_summary import build_acceptance_summary
from app.persistence.submission_store import SubmissionStore, create_submission_record
from app.persistence.acceptance_store import AcceptanceStore
from app.diagnostics.obligation_diagnostics import build_obligation_diagnostics
from app.evolution.submission_evolution import build_submission_evolution
from app.guidance.planner_guidance import build_planner_guidance


def _minimal_submission_record(submission_id: str, project_id: str, acceptability: str):
    """Minimal valid submission record for testing (no validator run)."""
    vr = {
        "acceptability_status": acceptability,
        "overall_status": "pass" if acceptability == "ACCEPTABLE" else "fail",
        "obligations_report": [{"id": "OBL-001", "aligned": acceptability == "ACCEPTABLE"}],
        "obligations_not_represented_but_mandatory": [] if acceptability == "ACCEPTABLE" else [{"id": "OBL-001", "required_action": "Add WBS"}],
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
    return SubmissionStore(tmp_dirs[0])


@pytest.fixture
def acceptance_store(tmp_dirs, submission_store):
    return AcceptanceStore(base_dir=tmp_dirs[1], submission_store=submission_store)


@pytest.fixture
def acceptable_submission(submission_store):
    """One stored submission: ACCEPTABLE."""
    rec = _minimal_submission_record("sub-acc-1", "proj-1", "ACCEPTABLE")
    submission_store.save(rec)
    return rec


@pytest.fixture
def not_acceptable_submission(submission_store):
    """One stored submission: NOT_ACCEPTABLE."""
    rec = _minimal_submission_record("sub-not-1", "proj-1", "NOT_ACCEPTABLE")
    submission_store.save(rec)
    return rec


def test_acceptable_submission_accept(
    submission_store,
    acceptance_store,
    acceptable_submission,
):
    """ACCEPTABLE submission → ACCEPT (allowed)."""
    acc_rec = create_acceptance_record(
        submission_id=acceptable_submission["submission_id"],
        project_id=acceptable_submission["project_id"],
        decision="ACCEPT",
        decided_by="Project Manager",
    )
    acceptance_store.save_acceptance(acc_rec)
    by_sub = acceptance_store.get_by_submission(acceptable_submission["submission_id"])
    assert len(by_sub) == 1
    assert by_sub[0]["decision"] == "ACCEPT"
    summary = build_acceptance_summary(
        acceptable_submission["submission_id"],
        submission_store=submission_store,
        acceptance_store=acceptance_store,
    )
    assert summary["acceptability_status"] == "ACCEPTABLE"
    assert summary["latest_acceptance_decision"]["decision"] == "ACCEPT"
    assert "do not alter acceptability" in summary["note"].lower()


def test_not_acceptable_submission_accept_with_comments_allowed(
    submission_store,
    acceptance_store,
    not_acceptable_submission,
):
    """NOT_ACCEPTABLE submission → ACCEPT_WITH_COMMENTS (allowed)."""
    acc_rec = create_acceptance_record(
        submission_id=not_acceptable_submission["submission_id"],
        project_id=not_acceptable_submission["project_id"],
        decision="ACCEPT_WITH_COMMENTS",
        decided_by="PM",
        comments="Proceeding with noted exceptions; TW to be submitted in v2.",
    )
    acceptance_store.save_acceptance(acc_rec)
    summary = build_acceptance_summary(
        not_acceptable_submission["submission_id"],
        submission_store=submission_store,
        acceptance_store=acceptance_store,
    )
    assert summary["acceptability_status"] == "NOT_ACCEPTABLE"
    assert summary["latest_acceptance_decision"]["decision"] == "ACCEPT_WITH_COMMENTS"
    assert summary["latest_acceptance_decision"]["comments"]


def test_acceptable_submission_not_accept_allowed(
    submission_store,
    acceptance_store,
    acceptable_submission,
):
    """ACCEPTABLE submission → NOT_ACCEPT (allowed)."""
    acc_rec = create_acceptance_record(
        submission_id=acceptable_submission["submission_id"],
        project_id=acceptable_submission["project_id"],
        decision="NOT_ACCEPT",
        decided_by="Client",
    )
    acceptance_store.save_acceptance(acc_rec)
    summary = build_acceptance_summary(
        acceptable_submission["submission_id"],
        submission_store=submission_store,
        acceptance_store=acceptance_store,
    )
    assert summary["acceptability_status"] == "ACCEPTABLE"
    assert summary["latest_acceptance_decision"]["decision"] == "NOT_ACCEPT"


def test_accept_with_comments_without_comments_runtime_error(
    acceptance_store,
    not_acceptable_submission,
):
    """ACCEPT_WITH_COMMENTS without comments → RuntimeError."""
    with pytest.raises(RuntimeError) as exc_info:
        create_acceptance_record(
            submission_id=not_acceptable_submission["submission_id"],
            project_id=not_acceptable_submission["project_id"],
            decision="ACCEPT_WITH_COMMENTS",
            decided_by="PM",
            comments="",
        )
    assert "comments" in str(exc_info.value).lower()
    with pytest.raises(RuntimeError):
        create_acceptance_record(
            submission_id=not_acceptable_submission["submission_id"],
            project_id=not_acceptable_submission["project_id"],
            decision="ACCEPT_WITH_COMMENTS",
            decided_by="PM",
        )


def test_acceptance_does_not_change_stored_acceptability(
    submission_store,
    acceptance_store,
    not_acceptable_submission,
):
    """Acceptance does not change stored acceptability."""
    acc_rec = create_acceptance_record(
        submission_id=not_acceptable_submission["submission_id"],
        project_id=not_acceptable_submission["project_id"],
        decision="ACCEPT_WITH_COMMENTS",
        decided_by="PM",
        comments="Accepted with comments.",
    )
    acceptance_store.save_acceptance(acc_rec)
    loaded = submission_store.get(not_acceptable_submission["submission_id"])
    assert loaded["validation_response"]["acceptability_status"] == "NOT_ACCEPTABLE"
    summary = build_acceptance_summary(
        not_acceptable_submission["submission_id"],
        submission_store=submission_store,
        acceptance_store=acceptance_store,
    )
    assert summary["acceptability_status"] == "NOT_ACCEPTABLE"


def test_acceptance_history_immutable_overwrite_raises(
    acceptance_store,
    not_acceptable_submission,
):
    """Acceptance history is immutable; overwrite raises RuntimeError."""
    acc_rec = create_acceptance_record(
        submission_id=not_acceptable_submission["submission_id"],
        project_id=not_acceptable_submission["project_id"],
        decision="NOT_ACCEPT",
        decided_by="PM",
    )
    acceptance_store.save_acceptance(acc_rec)
    with pytest.raises(RuntimeError) as exc_info:
        acceptance_store.save_acceptance(acc_rec)
    assert "immutable" in str(exc_info.value).lower() or "overwrite" in str(exc_info.value).lower()


def test_acceptance_summary_reflects_latest_decision_only(
    submission_store,
    acceptance_store,
    not_acceptable_submission,
):
    """Acceptance summary reflects latest decision only (by decided_at)."""
    r1 = create_acceptance_record(
        submission_id=not_acceptable_submission["submission_id"],
        project_id=not_acceptable_submission["project_id"],
        decision="NOT_ACCEPT",
        decided_by="PM",
    )
    acceptance_store.save_acceptance(r1)
    r2 = create_acceptance_record(
        submission_id=not_acceptable_submission["submission_id"],
        project_id=not_acceptable_submission["project_id"],
        decision="ACCEPT_WITH_COMMENTS",
        decided_by="PM",
        comments="Revised decision.",
    )
    acceptance_store.save_acceptance(r2)
    summary = build_acceptance_summary(
        not_acceptable_submission["submission_id"],
        submission_store=submission_store,
        acceptance_store=acceptance_store,
    )
    assert len(summary["acceptance_history"]) == 2
    assert summary["latest_acceptance_decision"]["decision"] == "ACCEPT_WITH_COMMENTS"


def test_acceptance_submission_id_must_exist(acceptance_store, submission_store):
    """Guard: submission_id must exist in SubmissionStore."""
    acc_rec = create_acceptance_record(
        submission_id="nonexistent-sub-id",
        project_id="proj-1",
        decision="ACCEPT",
        decided_by="PM",
    )
    with pytest.raises(RuntimeError) as exc_info:
        acceptance_store.save_acceptance(acc_rec)
    assert "does not exist" in str(exc_info.value) or "nonexistent" in str(exc_info.value).lower()
