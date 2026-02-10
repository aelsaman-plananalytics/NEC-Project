"""
Final integration test: evidence modes and single acceptability authority.

Contract: Obligation A (mandatory, PHRASE), Obligation B (mandatory, WBS_ONLY).
Programme: activities contain phrase evidence for both; WBS contains match string only for A, not B.

Asserts:
- Obligation A → aligned (phrase + WBS match).
- Obligation B → NOT aligned (WBS_ONLY, no "utilities diversions" in name or WBS).
- Programme → NOT ACCEPTABLE.
- Validation completes (no RuntimeError); report generated; no contradiction.

Fails if: phrase leakage into WBS_ONLY, WBS_ONLY is softened, or acceptability is overridden.
"""

import pytest

from app.p6_engine.comprehensive_validator import ComprehensiveValidator
from app.p6_engine.obligation_entities import EVIDENCE_MODE_PHRASE, EVIDENCE_MODE_WBS_ONLY


def _contract_phrase_and_wbs_only():
    """Contract with Obligation A (PHRASE), Obligation B (WBS_ONLY), and Temporary Works (WBS_ONLY), all mandatory."""
    return {
        "obligation_entities": {
            "obligations": [
                {
                    "id": "OBL-A",
                    "original_contract_text": "Programme submission",
                    "original_contract_texts": ["Programme submission"],
                    "canonical_name": "Programme submission",
                    "canonical_match_string": "programme submission",
                    "clause_references": [],
                    "facets": {"has_scope_component": True, "has_programme_duty": True, "has_governance_requirement": False, "has_timing_requirement": False},
                    "mandatory_for_acceptance": True,
                    "scope_classification": "ACTION_REQUIRED",
                    "evidence_mode": EVIDENCE_MODE_PHRASE,
                },
                {
                    "id": "OBL-B",
                    "original_contract_text": "Utilities Diversions",
                    "original_contract_texts": ["Utilities Diversions"],
                    "canonical_name": "Utilities Diversions",
                    "canonical_match_string": "utilities diversions",
                    "clause_references": [],
                    "facets": {"has_scope_component": True, "has_programme_duty": False, "has_governance_requirement": False, "has_timing_requirement": False},
                    "mandatory_for_acceptance": True,
                    "scope_classification": "ACTION_REQUIRED",
                    "evidence_mode": EVIDENCE_MODE_WBS_ONLY,
                },
                {
                    "id": "OBL-036",
                    "original_contract_text": "Temporary Works",
                    "original_contract_texts": ["Temporary Works"],
                    "canonical_name": "Temporary Works",
                    "canonical_match_string": "temporary works",
                    "clause_references": [],
                    "facets": {"has_scope_component": True, "has_programme_duty": False, "has_governance_requirement": False, "has_timing_requirement": False},
                    "mandatory_for_acceptance": True,
                    "scope_classification": "ACTION_REQUIRED",
                    "evidence_mode": EVIDENCE_MODE_WBS_ONLY,
                },
            ],
            "validation_error": None,
        },
        "scope_items": [],
        "programme_compliance_model": {},
        "constraints": [],
    }


def _programme_phrase_evidence_both_wbs_only_a():
    """
    Programme: phrase evidence for A and B; WBS match only for A and Temporary Works (not B).
    - WBS "Programme submission" → A evidenced (phrase + WBS).
    - WBS "Temporary Works" → Temporary Works evidenced (WBS_ONLY).
    - No "utilities diversions" in WBS or activity name → B must NOT be evidenced (WBS_ONLY).
    """
    return {
        "activities": [
            {"task_id": "1", "task_name": "Programme submission draft", "wbs_id": "1"},
            {"task_id": "2", "task_name": "Diversion works", "wbs_id": "2"},
            {"task_id": "3", "task_name": "TW activity", "wbs_id": "3"},
        ],
        "wbs": [
            {"wbs_id": "1", "parent_wbs_id": "", "wbs_name": "Programme submission"},
            {"wbs_id": "2", "parent_wbs_id": "", "wbs_name": "Works"},
            {"wbs_id": "3", "parent_wbs_id": "", "wbs_name": "Temporary Works"},
        ],
        "calendars": [],
        "logic": [],
        "constraints": [],
        "metadata": {},
    }


def test_evidence_modes_phrase_aligned_wbs_only_not_aligned_not_acceptable():
    """
    E2E: Obligation A (PHRASE) aligned; Obligation B (WBS_ONLY) not aligned; programme NOT ACCEPTABLE.
    Validation completes; report generated; no contradiction.
    """
    contract_data = _contract_phrase_and_wbs_only()
    p6_data = _programme_phrase_evidence_both_wbs_only_a()
    validator = ComprehensiveValidator()
    output = validator.validate(contract_data, p6_data)

    vs = output.get("validation_summary") or {}
    assert vs.get("acceptability_status") != "ACCEPTABLE", (
        "Programme must NOT be ACCEPTABLE when mandatory WBS_ONLY obligation B is not evidenced."
    )

    scope_cov = output.get("nec_alignment", {}).get("scope_coverage") or {}
    obligations_report = scope_cov.get("obligations_report") or []
    assert len(obligations_report) >= 3

    ob_a = next((o for o in obligations_report if o.get("id") == "OBL-A"), None)
    ob_b = next((o for o in obligations_report if o.get("id") == "OBL-B"), None)
    assert ob_a is not None and ob_b is not None

    assert ob_a.get("aligned") is True, "Obligation A (PHRASE) must be aligned (phrase + WBS evidence)."
    assert ob_b.get("aligned") is False, "Obligation B (WBS_ONLY) must NOT be aligned (no WBS/name match)."
    assert ob_b.get("evidenced_by_activities") is False, "WBS_ONLY obligation B must not be evidenced by phrase."

    # No contradiction: failure reasons should mention B, not A
    failure_reasons = vs.get("acceptability_failure_reasons") or []
    failure_text = " ".join(failure_reasons).lower()
    assert "utilities diversions" in failure_text or "obl-b" in failure_text or "not represented" in failure_text, (
        "Failure reasons should reference the non-aligned mandatory obligation."
    )

    # Report present
    assert scope_cov.get("obligation_entities_used") is True


# ---- Planner workflow: one PHRASE, one WBS_ONLY; Programme A = PHRASE only → NOT ACCEPTABLE; Programme B = both → ACCEPTABLE ----


def _contract_planner_workflow():
    """Contract with one PHRASE mandatory (Programme submission) and one WBS_ONLY mandatory (Temporary Works)."""
    from app.p6_engine.frozen_requirements import build_frozen_requirements
    contract_data = {
        "scope_items": [],
        "programme_compliance_model": {},
        "constraints": [],
    }
    frozen = build_frozen_requirements(contract_data)
    contract_data["obligation_entities"] = frozen["obligation_entities"]
    obligations = list((contract_data["obligation_entities"].get("obligations") or []))
    obligations.insert(0, {
        "id": "OBL-PHRASE",
        "original_contract_text": "Programme submission",
        "original_contract_texts": ["Programme submission"],
        "canonical_name": "Programme submission",
        "canonical_match_string": "programme submission",
        "clause_references": [],
        "facets": {"has_scope_component": True, "has_programme_duty": True, "has_governance_requirement": False, "has_timing_requirement": False},
        "mandatory_for_acceptance": True,
        "scope_classification": "ACTION_REQUIRED",
        "evidence_mode": EVIDENCE_MODE_PHRASE,
    })
    contract_data["obligation_entities"] = {"obligations": obligations, "validation_error": None}
    return contract_data


def _programme_a_phrase_only():
    """Satisfies PHRASE obligation only (Programme submission); no Temporary Works in WBS/name."""
    return {
        "activities": [
            {"task_id": "1", "task_name": "Programme submission draft", "wbs_id": "1"},
        ],
        "wbs": [{"wbs_id": "1", "parent_wbs_id": "", "wbs_name": "Programme submission"}],
        "calendars": [],
        "logic": [],
        "constraints": [],
        "metadata": {},
    }


def _programme_b_both():
    """Satisfies both: Programme submission (phrase/WBS) and Temporary Works (WBS)."""
    return {
        "activities": [
            {"task_id": "1", "task_name": "Programme submission draft", "wbs_id": "1"},
            {"task_id": "2", "task_name": "TW activity", "wbs_id": "2"},
        ],
        "wbs": [
            {"wbs_id": "1", "parent_wbs_id": "", "wbs_name": "Programme submission"},
            {"wbs_id": "2", "parent_wbs_id": "", "wbs_name": "Temporary Works"},
        ],
        "calendars": [],
        "logic": [],
        "constraints": [],
        "metadata": {},
    }


def test_planner_workflow_phrase_only_fails_both_pass():
    """
    E2E planner workflow: Contract has one PHRASE and one WBS_ONLY mandatory obligation.
    Programme A: satisfies PHRASE only → NOT ACCEPTABLE.
    Programme B: satisfies both → ACCEPTABLE.
    Asserts: correct acceptability, failure messaging for A, no RuntimeError, obligation_entities_used (no legacy engines).
    """
    contract_data = _contract_planner_workflow()
    validator = ComprehensiveValidator()

    # Programme A: PHRASE only
    output_a = validator.validate(contract_data, _programme_a_phrase_only())
    vs_a = output_a.get("validation_summary") or {}
    assert vs_a.get("acceptability_status") != "ACCEPTABLE", (
        "Programme A must NOT be ACCEPTABLE when only PHRASE obligation is satisfied (WBS_ONLY Temporary Works missing)."
    )
    scope_cov_a = output_a.get("nec_alignment", {}).get("scope_coverage") or {}
    assert scope_cov_a.get("obligation_entities_used") is True, "Obligation engine must be used (no legacy)."
    failure_reasons_a = vs_a.get("acceptability_failure_reasons") or []
    assert any("temporary works" in r.lower() or "not represented" in r.lower() for r in failure_reasons_a), (
        "Failure reasons must mention the missing mandatory obligation (Temporary Works)."
    )
    not_rep = scope_cov_a.get("obligations_not_represented_but_mandatory") or []
    tw_not_rep = next((o for o in not_rep if (o.get("original_contract_text") or "").strip().lower() == "temporary works"), None)
    assert tw_not_rep is not None
    assert tw_not_rep.get("required_action"), "Unaligned mandatory obligation must have required_action for planners."
    assert "temporary works" in (tw_not_rep.get("canonical_match_string") or "").lower()

    # Programme B: both
    output_b = validator.validate(contract_data, _programme_b_both())
    vs_b = output_b.get("validation_summary") or {}
    assert vs_b.get("acceptability_status") == "ACCEPTABLE", (
        "Programme B must be ACCEPTABLE when both PHRASE and WBS_ONLY obligations are satisfied."
    )
    scope_cov_b = output_b.get("nec_alignment", {}).get("scope_coverage") or {}
    assert scope_cov_b.get("obligation_entities_used") is True
    assert not (vs_b.get("acceptability_failure_reasons") or []), "Acceptable programme must have no failure reasons."
