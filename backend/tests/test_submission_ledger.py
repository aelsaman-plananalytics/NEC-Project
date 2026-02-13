"""
Tests for submission ledger hash chaining (Step 3C).
Persistence layer only; no changes to acceptability or review pack.
"""

import json
import pytest

from app.persistence.submission_store import SubmissionStore, create_submission_record
from app.diagnostics.obligation_diagnostics import build_obligation_diagnostics
from app.evolution.submission_evolution import build_submission_evolution
from app.guidance.planner_guidance import build_planner_guidance
from app.storage.local_storage import LocalStorage


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
def store(tmp_path):
    base = tmp_path / "submissions"
    base.mkdir()
    return SubmissionStore(storage=LocalStorage(base))


def _store_base_path(store):
    """Return the base Path for the store's LocalStorage (for tests that need to open files by path)."""
    return store._storage._base


def test_first_submission_has_no_previous_hash(store):
    """Create submission without previous_submission_id; previous_record_hash is None."""
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
        previous_submission_id=None,
        submission_id="sub-first",
    )
    assert record.get("previous_record_hash") is None
    store.save(record)
    loaded = store.get("sub-first")
    assert loaded is not None
    assert loaded.get("previous_record_hash") is None


def test_second_submission_links_to_previous_hash(store):
    """Create v1, then v2 with previous_submission_id=v1; v2.previous_record_hash == v1.record_hash."""
    vr = _valid_vr()
    r1 = create_submission_record(
        project_id="proj-1",
        programme_name="Programme A",
        submission_stage="initial",
        validation_response=vr,
        planner_assumptions_used=[],
        diagnostics_output=build_obligation_diagnostics(vr),
        evolution_output=build_submission_evolution(vr),
        planner_guidance_output=build_planner_guidance(vr),
        submission_id="sub-v1",
    )
    store.save(r1)
    v1_hash = r1["record_hash"]
    r2 = create_submission_record(
        project_id="proj-1",
        programme_name="Programme A",
        submission_stage="interim",
        validation_response=vr,
        planner_assumptions_used=[],
        diagnostics_output=build_obligation_diagnostics(vr),
        evolution_output=build_submission_evolution(vr),
        planner_guidance_output=build_planner_guidance(vr),
        previous_submission_id="sub-v1",
        submission_id="sub-v2",
        submission_store=store,
    )
    assert r2["previous_record_hash"] == v1_hash
    store.save(r2)
    loaded = store.get("sub-v2")
    assert loaded["previous_record_hash"] == v1_hash


def test_chain_break_if_previous_deleted(store):
    """Create v1 and v2; delete v1 JSON; loading v2 raises RuntimeError('Ledger chain broken')."""
    vr = _valid_vr()
    r1 = create_submission_record(
        project_id="proj-1",
        programme_name="Programme A",
        submission_stage="initial",
        validation_response=vr,
        planner_assumptions_used=[],
        diagnostics_output=build_obligation_diagnostics(vr),
        evolution_output=build_submission_evolution(vr),
        planner_guidance_output=build_planner_guidance(vr),
        submission_id="sub-v1",
    )
    store.save(r1)
    r2 = create_submission_record(
        project_id="proj-1",
        programme_name="Programme A",
        submission_stage="interim",
        validation_response=vr,
        planner_assumptions_used=[],
        diagnostics_output=build_obligation_diagnostics(vr),
        evolution_output=build_submission_evolution(vr),
        planner_guidance_output=build_planner_guidance(vr),
        previous_submission_id="sub-v1",
        submission_id="sub-v2",
        submission_store=store,
    )
    store.save(r2)
    base = _store_base_path(store)
    path_v1 = base / store._path("sub-v1")
    path_v1.unlink()
    with pytest.raises(RuntimeError) as exc_info:
        store.get("sub-v2")
    assert "Ledger chain broken" in str(exc_info.value)


def test_chain_break_if_previous_tampered(store):
    """Create v1 and v2; modify v1 JSON (e.g. programme_name) and recompute v1 hash; loading v2 raises Ledger chain integrity violation."""
    from app.persistence.integrity import compute_record_hash
    vr = _valid_vr()
    r1 = create_submission_record(
        project_id="proj-1",
        programme_name="Programme A",
        submission_stage="initial",
        validation_response=vr,
        planner_assumptions_used=[],
        diagnostics_output=build_obligation_diagnostics(vr),
        evolution_output=build_submission_evolution(vr),
        planner_guidance_output=build_planner_guidance(vr),
        submission_id="sub-v1",
    )
    store.save(r1)
    r2 = create_submission_record(
        project_id="proj-1",
        programme_name="Programme A",
        submission_stage="interim",
        validation_response=vr,
        planner_assumptions_used=[],
        diagnostics_output=build_obligation_diagnostics(vr),
        evolution_output=build_submission_evolution(vr),
        planner_guidance_output=build_planner_guidance(vr),
        previous_submission_id="sub-v1",
        submission_id="sub-v2",
        submission_store=store,
    )
    store.save(r2)
    base = _store_base_path(store)
    path_v1 = base / store._path("sub-v1")
    with open(path_v1, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["programme_name"] = "Programme Tampered"
    data["record_hash"] = compute_record_hash(data)
    with open(path_v1, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    with pytest.raises(RuntimeError) as exc_info:
        store.get("sub-v2")
    assert "Ledger chain integrity violation" in str(exc_info.value) or "previous record hash mismatch" in str(exc_info.value).lower()
