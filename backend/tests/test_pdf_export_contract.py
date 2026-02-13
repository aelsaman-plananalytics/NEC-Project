"""
Tests for PDF export contract and builder (Step 4B.1).

No validator, no PDF rendering. Contract and builder only.
"""

import pytest

from app.review.pdf_export_contract import (
    PDF_EXPORT_SECTION_ORDER,
    REVIEW_PACK_REQUIRED_KEYS,
    LEGAL_ACCEPTABILITY_NOTE,
    GOVERNANCE_NOTE,
)
from app.review.pdf_export_builder import build_pdf_export_input
from app.review.programme_review_pack import build_programme_review_pack
from app.persistence.submission_store import SubmissionStore, create_submission_record
from app.persistence.acceptance_store import AcceptanceStore
from app.storage.local_storage import LocalStorage
from app.diagnostics.obligation_diagnostics import build_obligation_diagnostics
from app.evolution.submission_evolution import build_submission_evolution
from app.guidance.planner_guidance import build_planner_guidance


def _review_pack_not_acceptable(submission_store, acceptance_store, submission_id: str = "sub-not"):
    """Build a valid NOT_ACCEPTABLE review pack (one blocker)."""
    vr = {
        "acceptability_status": "NOT_ACCEPTABLE",
        "overall_status": "fail",
        "obligations_report": [
            {
                "id": "OBL-001",
                "aligned": False,
                "mandatory_for_acceptance": True,
                "original_contract_text": "Temporary Works",
                "evidence_mode": "WBS_ONLY",
                "canonical_match_string": "temporary works",
                "required_action": "Add WBS containing 'temporary works'",
            },
        ],
        "obligations_not_represented_but_mandatory": [
            {"id": "OBL-001", "original_contract_text": "Temporary Works", "required_action": "Add WBS containing 'temporary works'"},
        ],
    }
    rec = create_submission_record(
        project_id="proj-1",
        programme_name="Programme A",
        submission_stage="initial",
        validation_response=vr,
        planner_assumptions_used=[],
        diagnostics_output=build_obligation_diagnostics(vr),
        evolution_output=build_submission_evolution(vr),
        planner_guidance_output=build_planner_guidance(vr),
        submission_id=submission_id,
    )
    submission_store.save(rec)
    return build_programme_review_pack(submission_id, submission_store, acceptance_store)


def _review_pack_acceptable(submission_store, acceptance_store, submission_id: str = "sub-acc"):
    """Build a valid ACCEPTABLE review pack (no blockers)."""
    vr = {
        "acceptability_status": "ACCEPTABLE",
        "overall_status": "pass",
        "obligations_report": [
            {"id": "OBL-001", "aligned": True, "mandatory_for_acceptance": True, "original_contract_text": "Temporary Works"},
        ],
        "obligations_not_represented_but_mandatory": [],
    }
    rec = create_submission_record(
        project_id="proj-1",
        programme_name="Programme A",
        submission_stage="initial",
        validation_response=vr,
        planner_assumptions_used=[],
        diagnostics_output=build_obligation_diagnostics(vr),
        evolution_output=build_submission_evolution(vr),
        planner_guidance_output=build_planner_guidance(vr),
        submission_id=submission_id,
    )
    submission_store.save(rec)
    return build_programme_review_pack(submission_id, submission_store, acceptance_store)


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


def test_not_acceptable_submission_pdf_input_contains_blockers_table(
    submission_store,
    acceptance_store,
    request,
):
    """NOT_ACCEPTABLE submission → PDF input contains blockers table."""
    sid = f"sub-not-{request.node.name}"
    pack = _review_pack_not_acceptable(submission_store, acceptance_store, submission_id=sid)
    pdf_input = build_pdf_export_input(pack)

    assert pdf_input["legal_acceptability"]["acceptability_status"] == "NOT_ACCEPTABLE"
    mos = pdf_input["mandatory_obligations_status"]
    assert mos["total_mandatory"] == 1
    assert mos["aligned_count"] == 0
    assert mos["not_aligned_count"] == 1
    assert len(mos["not_represented"]) == 1
    assert mos["not_represented"][0]["obligation_name"] == "Temporary Works"
    assert mos["not_represented"][0]["required_action"] == "Add WBS containing 'temporary works'"
    assert mos["not_represented"][0]["evidence_mode"] == "WBS_ONLY"


def test_acceptable_submission_pdf_input_blockers_table_empty(
    submission_store,
    acceptance_store,
    request,
):
    """ACCEPTABLE submission → blockers table empty."""
    sid = f"sub-acc-{request.node.name}"
    pack = _review_pack_acceptable(submission_store, acceptance_store, submission_id=sid)
    pdf_input = build_pdf_export_input(pack)

    assert pdf_input["legal_acceptability"]["acceptability_status"] == "ACCEPTABLE"
    assert pdf_input["mandatory_obligations_status"]["not_represented"] == []
    assert pdf_input["mandatory_obligations_status"]["aligned_count"] == 1
    assert pdf_input["mandatory_obligations_status"]["not_aligned_count"] == 0


def test_governance_accept_on_not_acceptable_pdf_shows_both_without_conflict(
    submission_store,
    acceptance_store,
    request,
):
    """Governance ACCEPT on NOT_ACCEPTABLE → PDF shows both without conflict."""
    sid = f"sub-not-{request.node.name}"
    pack = _review_pack_not_acceptable(submission_store, acceptance_store, submission_id=sid)
    from app.governance.acceptance_records import create_acceptance_record
    acc = create_acceptance_record(
        submission_id=sid,
        project_id="proj-1",
        decision="ACCEPT_WITH_COMMENTS",
        decided_by="PM",
        comments="Accepted with exceptions.",
    )
    acceptance_store.save_acceptance(acc)
    pack = build_programme_review_pack(sid, submission_store, acceptance_store)
    pdf_input = build_pdf_export_input(pack)

    assert pdf_input["legal_acceptability"]["acceptability_status"] == "NOT_ACCEPTABLE"
    assert pdf_input["governance"]["latest_acceptance_decision"] == "ACCEPT_WITH_COMMENTS"
    assert pdf_input["governance"]["latest_acceptance_comments"] == "Accepted with exceptions."
    assert len(pdf_input["mandatory_obligations_status"]["not_represented"]) == 1


def test_runtime_error_if_acceptable_and_blockers():
    """RuntimeError if ACCEPTABLE and not_represented non-empty (contradiction)."""
    pack = {
        "review_metadata": {"submission_id": "x", "project_id": "p", "programme_name": "P", "submission_stage": "initial", "created_at": "2025-01-01T00:00:00Z", "previous_submission_id": None},
        "acceptability_section": {"acceptability_status": "ACCEPTABLE", "overall_status": "pass", "legal_note": "x"},
        "mandatory_obligations_status": {
            "total_mandatory": 1,
            "aligned": 0,
            "not_aligned": 1,
            "not_represented": [{"obligation_name": "X", "evidence_mode": "WBS_ONLY", "canonical_match_string": "x", "required_action": "Add X"}],
        },
        "planner_guidance": {"planner_guidance": {"since_last_submission": {}, "required_before_next_submission": [], "advisory_notes": []}},
        "submission_evolution": {"obligation_changes": {"became_aligned": [], "became_unaligned": []}},
        "diagnostics_summary": {"diagnostics_summary": "x", "failure_table": []},
        "governance": {"latest_acceptance_decision": None, "latest_acceptance_comments": None, "acceptance_history": [], "governance_note": "x"},
    }
    with pytest.raises(RuntimeError) as exc_info:
        build_pdf_export_input(pack)
    assert "ACCEPTABLE" in str(exc_info.value) and "not_represented" in str(exc_info.value).lower()


def test_pdf_export_input_section_order_and_no_extra_fields(
    submission_store,
    acceptance_store,
    request,
):
    """Snapshot-style: output has exact section order and no unexpected added/removed top-level fields."""
    sid = f"sub-acc-{request.node.name}"
    pack = _review_pack_acceptable(submission_store, acceptance_store, submission_id=sid)
    pdf_input = build_pdf_export_input(pack)

    top_level = list(pdf_input.keys())
    assert top_level == PDF_EXPORT_SECTION_ORDER, "PDF export sections must match contract order"

    assert "cover" in pdf_input
    assert set(pdf_input["cover"].keys()) == {"project_id", "programme_name", "submission_stage", "submission_id", "created_at", "previous_submission_id"}

    assert pdf_input["legal_acceptability"]["legal_note"] == LEGAL_ACCEPTABILITY_NOTE
    assert pdf_input["governance"]["governance_note"] == GOVERNANCE_NOTE

    assert "mandatory_obligations_status" in pdf_input
    mos = pdf_input["mandatory_obligations_status"]
    assert set(mos.keys()) == {"total_mandatory", "aligned_count", "not_aligned_count", "not_represented"}

    assert set(pdf_input["planner_guidance"].keys()) == {"required_before_next_submission", "resolved_obligations", "unchanged_blockers", "advisory_notes"}
    assert set(pdf_input["submission_evolution"].keys()) == {"status_change", "became_aligned", "became_unaligned"}
    assert set(pdf_input["diagnostics_summary"].keys()) == {"diagnostics_summary", "failure_table"}
    assert set(pdf_input["governance"].keys()) == {"latest_acceptance_decision", "latest_acceptance_comments", "acceptance_history", "governance_note"}


def test_build_pdf_export_input_rejects_non_review_pack():
    """Passing non-Programme Review Pack (missing keys) → RuntimeError."""
    with pytest.raises(RuntimeError) as exc_info:
        build_pdf_export_input({"review_metadata": {}})
    assert "Missing required keys" in str(exc_info.value)
    with pytest.raises(RuntimeError):
        build_pdf_export_input("not a dict")
    with pytest.raises(RuntimeError):
        build_pdf_export_input(None)


def test_runtime_error_if_required_action_missing_for_not_represented():
    """RuntimeError if any not_represented row has missing required_action."""
    pack = {
        "review_metadata": {"submission_id": "x", "project_id": "p", "programme_name": "P", "submission_stage": "initial", "created_at": "2025-01-01T00:00:00Z", "previous_submission_id": None},
        "acceptability_section": {"acceptability_status": "NOT_ACCEPTABLE", "overall_status": "fail", "legal_note": "x"},
        "mandatory_obligations_status": {
            "total_mandatory": 1,
            "aligned": 0,
            "not_aligned": 1,
            "not_represented": [{"obligation_name": "X", "evidence_mode": "WBS_ONLY", "canonical_match_string": "x", "required_action": None}],
        },
        "planner_guidance": {"planner_guidance": {"since_last_submission": {}, "required_before_next_submission": [], "advisory_notes": []}},
        "submission_evolution": {"obligation_changes": {"became_aligned": [], "became_unaligned": []}},
        "diagnostics_summary": {"diagnostics_summary": "x", "failure_table": []},
        "governance": {"latest_acceptance_decision": None, "latest_acceptance_comments": None, "acceptance_history": [], "governance_note": "x"},
    }
    with pytest.raises(RuntimeError) as exc_info:
        build_pdf_export_input(pack)
    assert "required_action" in str(exc_info.value).lower()


def test_runtime_error_if_counts_dont_reconcile():
    """RuntimeError if aligned + not_aligned != total_mandatory."""
    pack = {
        "review_metadata": {"submission_id": "x", "project_id": "p", "programme_name": "P", "submission_stage": "initial", "created_at": "2025-01-01T00:00:00Z", "previous_submission_id": None},
        "acceptability_section": {"acceptability_status": "NOT_ACCEPTABLE", "overall_status": "fail", "legal_note": "x"},
        "mandatory_obligations_status": {
            "total_mandatory": 2,
            "aligned": 1,
            "not_aligned": 0,
            "not_represented": [],
        },
        "planner_guidance": {"planner_guidance": {"since_last_submission": {}, "required_before_next_submission": [], "advisory_notes": []}},
        "submission_evolution": {"obligation_changes": {"became_aligned": [], "became_unaligned": []}},
        "diagnostics_summary": {"diagnostics_summary": "x", "failure_table": []},
        "governance": {"latest_acceptance_decision": None, "latest_acceptance_comments": None, "acceptance_history": [], "governance_note": "x"},
    }
    with pytest.raises(RuntimeError) as exc_info:
        build_pdf_export_input(pack)
    assert "reconcile" in str(exc_info.value).lower()
