"""
Tests for tamper-evident integrity hashing of submission and acceptance records.
Persistence hardening only; no changes to acceptability or business logic.
"""

import json
import pytest

from pathlib import Path

from app.persistence.submission_store import SubmissionStore, create_submission_record
from app.persistence.acceptance_store import AcceptanceStore
from app.governance.acceptance_records import create_acceptance_record
from app.storage.local_storage import LocalStorage
from app.diagnostics.obligation_diagnostics import build_obligation_diagnostics
from app.evolution.submission_evolution import build_submission_evolution
from app.guidance.planner_guidance import build_planner_guidance


def _valid_vr():
    return {
        "acceptability_status": "NOT_ACCEPTABLE",
        "overall_status": "fail",
        "obligations_report": [
            {"id": "OBL-001", "aligned": False, "mandatory_for_acceptance": True, "original_contract_text": "Temporary Works"},
        ],
        "obligations_not_represented_but_mandatory": [
            {"id": "OBL-001", "original_contract_text": "Temporary Works", "required_action": "Add WBS"},
        ],
    }


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


def test_submission_hash_roundtrip(submission_store):
    """Create record, save, load; record_hash is unchanged."""
    vr = _valid_vr()
    record = create_submission_record(
        project_id="proj-1",
        programme_name="Programme A",
        submission_stage="initial",
        validation_response=vr,
        planner_assumptions_used=[],
        diagnostics_output=build_obligation_diagnostics(vr),
        evolution_output=build_submission_evolution(vr),
        planner_guidance_output=build_planner_guidance(vr),
        submission_id="sub-integrity",
    )
    original_hash = record["record_hash"]
    assert original_hash
    submission_store.save(record)
    loaded = submission_store.get("sub-integrity")
    assert loaded is not None
    assert loaded["record_hash"] == original_hash


def test_submission_tamper_detection(submission_store, tmp_dirs):
    """Save record, manually modify JSON (change acceptability_status), load → RuntimeError."""
    vr = _valid_vr()
    record = create_submission_record(
        project_id="proj-1",
        programme_name="Programme A",
        submission_stage="initial",
        validation_response=vr,
        planner_assumptions_used=[],
        diagnostics_output=build_obligation_diagnostics(vr),
        evolution_output=build_submission_evolution(vr),
        planner_guidance_output=build_planner_guidance(vr),
        submission_id="sub-tamper",
    )
    submission_store.save(record)
    path = Path(tmp_dirs[0]) / submission_store._path("sub-tamper")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["validation_response"] = dict(data["validation_response"])
    data["validation_response"]["acceptability_status"] = "ACCEPTABLE"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    with pytest.raises(RuntimeError) as exc_info:
        submission_store.get("sub-tamper")
    assert "Integrity check failed" in str(exc_info.value) or "modified" in str(exc_info.value).lower()


def test_acceptance_hash_roundtrip(submission_store, acceptance_store):
    """Create and save submission, create and save acceptance, load; record_hash unchanged."""
    vr = _valid_vr()
    sub_rec = create_submission_record(
        project_id="proj-1",
        programme_name="Programme A",
        submission_stage="initial",
        validation_response=vr,
        planner_assumptions_used=[],
        diagnostics_output=build_obligation_diagnostics(vr),
        evolution_output=build_submission_evolution(vr),
        planner_guidance_output=build_planner_guidance(vr),
        submission_id="sub-acc-int",
    )
    submission_store.save(sub_rec)
    acc_rec = create_acceptance_record(
        submission_id="sub-acc-int",
        project_id="proj-1",
        decision="NOT_ACCEPT",
        decided_by="PM",
        comments=None,
    )
    original_hash = acc_rec["record_hash"]
    assert original_hash
    acceptance_store.save_acceptance(acc_rec)
    loaded_list = acceptance_store.get_by_submission("sub-acc-int")
    assert len(loaded_list) == 1
    assert loaded_list[0]["record_hash"] == original_hash


def test_acceptance_tamper_detection(submission_store, acceptance_store, tmp_dirs):
    """Save acceptance, manually modify JSON (change decision), load → RuntimeError."""
    vr = _valid_vr()
    sub_rec = create_submission_record(
        project_id="proj-1",
        programme_name="Programme A",
        submission_stage="initial",
        validation_response=vr,
        planner_assumptions_used=[],
        diagnostics_output=build_obligation_diagnostics(vr),
        evolution_output=build_submission_evolution(vr),
        planner_guidance_output=build_planner_guidance(vr),
        submission_id="sub-acc-tamper",
    )
    submission_store.save(sub_rec)
    acc_rec = create_acceptance_record(
        submission_id="sub-acc-tamper",
        project_id="proj-1",
        decision="NOT_ACCEPT",
        decided_by="PM",
    )
    acceptance_store.save_acceptance(acc_rec)
    # Find the acceptance file (by acceptance_id)
    acc_id = acc_rec["acceptance_id"]
    path = Path(tmp_dirs[1]) / acceptance_store._path(acc_id)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["decision"] = "ACCEPT"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    with pytest.raises(RuntimeError) as exc_info:
        acceptance_store.get_by_submission("sub-acc-tamper")
    assert "Integrity check failed" in str(exc_info.value) or "modified" in str(exc_info.value).lower()
