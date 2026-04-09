"""
Tests for the planner lifecycle layer (Layer 2). Acceptability logic is unchanged.

- Lifecycle prep does not change acceptability outcome.
- Programmes can evolve NOT ACCEPTABLE → ACCEPTABLE across submissions.
- Assumptions affect workflow visibility but not legal acceptability (WBS_ONLY cannot be bypassed).
- Stage and readiness are additive only.
"""

import pytest

from app.p6_engine.comprehensive_validator import ComprehensiveValidator
from app.p6_engine.frozen_requirements import build_frozen_requirements
from app.p6_engine.submission_lifecycle import (
    prepare_contract_for_validation,
    get_stage_expectations,
    compute_obligation_readiness,
    apply_stage_to_obligations,
    merge_planner_assumptions,
    SUBMISSION_STAGE_FIRST_PROGRAMME,
    SUBMISSION_STAGE_REVISED_PROGRAMME,
)


def _contract_with_temporary_works():
    contract_data = {
        "scope_items": [
            {
                "text": "Utilities Diversions",
                "mandatory_for_acceptance": True,
                "evidence_mode": "WBS_ONLY",
                "canonical_match_string": "utilities diversions",
            }
        ],
        "programme_compliance_model": {},
        "constraints": [],
    }
    frozen = build_frozen_requirements(contract_data)
    contract_data["obligation_entities"] = frozen["obligation_entities"]
    return contract_data


def test_lifecycle_prep_does_not_change_acceptability():
    """Prepare_contract_for_validation with no stage/assumptions leaves acceptability unchanged."""
    contract_data = _contract_with_temporary_works()
    p6_no_tw = {
        "activities": [{"task_id": "1", "task_name": "Design", "wbs_id": "1"}],
        "wbs": [{"wbs_id": "1", "parent_wbs_id": "", "wbs_name": "Design"}],
        "calendars": [], "logic": [], "constraints": [], "metadata": {},
    }
    validator = ComprehensiveValidator()
    out_raw = validator.validate(contract_data, p6_no_tw)
    prepared = prepare_contract_for_validation(contract_data, None, None)
    out_prepared = validator.validate(prepared, p6_no_tw)
    assert out_raw.get("validation_summary", {}).get("acceptability_status") == out_prepared.get("validation_summary", {}).get("acceptability_status")
    assert out_raw.get("validation_summary", {}).get("acceptability_status") != "ACCEPTABLE"


def test_programme_evolution_not_acceptable_then_acceptable():
    """Same contract: programme without obligation → NOT ACCEPTABLE; programme with obligation → ACCEPTABLE."""
    contract_data = _contract_with_temporary_works()
    validator = ComprehensiveValidator()
    p6_no_tw = {
        "activities": [{"task_id": "1", "task_name": "Design", "wbs_id": "1"}],
        "wbs": [{"wbs_id": "1", "parent_wbs_id": "", "wbs_name": "Design"}],
        "calendars": [], "logic": [], "constraints": [], "metadata": {},
    }
    p6_with_tw = {
        "activities": [
            {"task_id": "1", "task_name": "Design", "wbs_id": "1"},
            {"task_id": "2", "task_name": "Diversions activity", "wbs_id": "2"},
        ],
        "wbs": [
            {"wbs_id": "1", "parent_wbs_id": "", "wbs_name": "Design"},
            {"wbs_id": "2", "parent_wbs_id": "", "wbs_name": "Utilities Diversions"},
        ],
        "calendars": [], "logic": [], "constraints": [], "metadata": {},
    }
    out1 = validator.validate(contract_data, p6_no_tw)
    out2 = validator.validate(contract_data, p6_with_tw)
    assert out1.get("validation_summary", {}).get("acceptability_status") != "ACCEPTABLE"
    assert out2.get("validation_summary", {}).get("acceptability_status") == "ACCEPTABLE"


def test_assumptions_do_not_bypass_wbs_only():
    """Planner assumption 'covered by later submission' on a WBS_ONLY obligation does NOT make programme ACCEPTABLE."""
    contract_data = _contract_with_temporary_works()
    obligations = list((contract_data["obligation_entities"].get("obligations") or []))
    ob_id = next((o["id"] for o in obligations if (o.get("original_contract_text") or "").strip().lower() == "utilities diversions"), None)
    assert ob_id
    contract_data = prepare_contract_for_validation(contract_data, None, [
        {"obligation_id": ob_id, "assumption_type": "covered_by_later_submission", "rationale": "To be submitted later"},
    ])
    p6_no_tw = {
        "activities": [{"task_id": "1", "task_name": "Design", "wbs_id": "1"}],
        "wbs": [{"wbs_id": "1", "parent_wbs_id": "", "wbs_name": "Design"}],
        "calendars": [], "logic": [], "constraints": [], "metadata": {},
    }
    validator = ComprehensiveValidator()
    out = validator.validate(contract_data, p6_no_tw)
    assert out.get("validation_summary", {}).get("acceptability_status") != "ACCEPTABLE", (
        "WBS_ONLY obligation cannot be satisfied by 'covered by later submission'; programme must still FAIL."
    )


def test_stage_expectations_returned():
    """get_stage_expectations returns non-empty string for known stages."""
    assert "first" in get_stage_expectations(SUBMISSION_STAGE_FIRST_PROGRAMME).lower()
    assert "revised" in get_stage_expectations(SUBMISSION_STAGE_REVISED_PROGRAMME).lower()
    assert len(get_stage_expectations(None)) > 0


def test_obligation_readiness_computed():
    """compute_obligation_readiness returns list with required_now and required_from_stage."""
    contract_data = _contract_with_temporary_works()
    obligations = (contract_data.get("obligation_entities") or {}).get("obligations") or []
    readiness = compute_obligation_readiness(obligations, SUBMISSION_STAGE_FIRST_PROGRAMME)
    assert len(readiness) == len(obligations)
    for r in readiness:
        assert "obligation_id" in r and "required_now" in r and "required_from_stage" in r
    ob_readiness = next((r for r in readiness if "utilities" in (r.get("obligation_name") or "").lower()), None)
    assert ob_readiness is not None
    assert ob_readiness["required_now"] is True  # no required_from_stage => required from first


def test_stage_activation_deactivates_later_obligations():
    """When required_from_stage is set, apply_stage_to_obligations sets mandatory_for_acceptance False for later stages."""
    obligations = [
        {"id": "OBL-1", "mandatory_for_acceptance": True, "required_from_stage": SUBMISSION_STAGE_REVISED_PROGRAMME},
    ]
    applied = apply_stage_to_obligations(obligations, SUBMISSION_STAGE_FIRST_PROGRAMME)
    assert applied[0]["mandatory_for_acceptance"] is False
    applied2 = apply_stage_to_obligations(obligations, SUBMISSION_STAGE_REVISED_PROGRAMME)
    assert applied2[0]["mandatory_for_acceptance"] is True
