"""
Regression tests: Temporary Works mandatory obligation and evidence-mode system.

- Test A: Contract includes Temporary Works, programme has NO Temporary Works WBS → NOT ACCEPTABLE.
- Test B: Same contract, programme HAS Temporary Works WBS → ACCEPTABLE.
- Test C: Programme has activities containing "works" but NO "temporary works" in name or WBS → NOT ACCEPTABLE (guards against generic phrase matching).
- Test D (generic evidence_mode): WBS_ONLY obligation is NOT evidenced by phrase tokens; evidenced only by name/WBS containing obligation text.

If any flips, CI must fail.
"""

import pytest

from app.p6_engine.frozen_requirements import build_frozen_requirements
from app.p6_engine.comprehensive_validator import ComprehensiveValidator
from app.p6_engine.obligation_entities import EVIDENCE_MODE_WBS_ONLY


def _contract_data_with_temporary_works():
    """Contract that yields obligation_entities including mandatory 'Temporary Works' (injection)."""
    contract_data = {
        "scope_items": [],
        "programme_compliance_model": {},
        "constraints": [],
    }
    frozen = build_frozen_requirements(contract_data)
    contract_data["obligation_entities"] = frozen["obligation_entities"]
    return contract_data


def _p6_data_without_temporary_works_wbs():
    """Programme with no activity whose WBS path contains 'Temporary Works'."""
    return {
        "activities": [
            {"task_id": "1", "task_name": "Design", "wbs_id": "1"},
        ],
        "wbs": [
            {"wbs_id": "1", "parent_wbs_id": "", "wbs_name": "Design"},
        ],
        "calendars": [],
        "logic": [],
        "constraints": [],
        "metadata": {},
    }


def _p6_data_with_temporary_works_wbs():
    """Programme with at least one activity whose WBS path contains 'Temporary Works'."""
    return {
        "activities": [
            {"task_id": "1", "task_name": "Design", "wbs_id": "1"},
            {"task_id": "2", "task_name": "TW activity", "wbs_id": "2"},
        ],
        "wbs": [
            {"wbs_id": "1", "parent_wbs_id": "", "wbs_name": "Design"},
            {"wbs_id": "2", "parent_wbs_id": "", "wbs_name": "Temporary Works"},
        ],
        "calendars": [],
        "logic": [],
        "constraints": [],
        "metadata": {},
    }


def _p6_data_with_works_but_no_temporary_works():
    """Programme with activities containing 'works' but no 'temporary works' in name or WBS. Must NOT evidence Temporary Works."""
    return {
        "activities": [
            {"task_id": "1", "task_name": "Design", "wbs_id": "1"},
            {"task_id": "2", "task_name": "Construction works", "wbs_id": "2"},
            {"task_id": "3", "task_name": "Permanent works package", "wbs_id": "2"},
        ],
        "wbs": [
            {"wbs_id": "1", "parent_wbs_id": "", "wbs_name": "Design"},
            {"wbs_id": "2", "parent_wbs_id": "", "wbs_name": "Works"},
        ],
        "calendars": [],
        "logic": [],
        "constraints": [],
        "metadata": {},
    }


def test_a_contract_includes_tw_programme_no_tw_wbs_not_acceptable():
    """
    Test A: Contract includes Temporary Works, programme has NO Temporary Works WBS.
    Result: NOT ACCEPTABLE.
    """
    contract_data = _contract_data_with_temporary_works()
    p6_data = _p6_data_without_temporary_works_wbs()
    validator = ComprehensiveValidator()
    output = validator.validate(contract_data, p6_data)
    vs = output.get("validation_summary") or {}
    assert vs.get("acceptability_status") != "ACCEPTABLE", (
        "Programme without Temporary Works WBS must NOT be ACCEPTABLE."
    )
    # Validator returns nec_alignment; router renames to alignment
    assert output.get("nec_alignment", {}).get("scope_coverage", {}).get("obligation_entities_used") is True


def test_b_same_contract_programme_has_tw_wbs_acceptable():
    """
    Test B: Same contract, programme HAS Temporary Works WBS.
    Result: ACCEPTABLE.
    """
    contract_data = _contract_data_with_temporary_works()
    p6_data = _p6_data_with_temporary_works_wbs()
    validator = ComprehensiveValidator()
    output = validator.validate(contract_data, p6_data)
    vs = output.get("validation_summary") or {}
    assert vs.get("acceptability_status") == "ACCEPTABLE", (
        "Programme with Temporary Works WBS must be ACCEPTABLE (when no other mandatory failures)."
    )
    scope_cov = output.get("nec_alignment", {}).get("scope_coverage") or {}
    assert scope_cov.get("obligation_entities_used") is True
    obligations_report = scope_cov.get("obligations_report") or []
    tw_obligations = [
        o for o in obligations_report
        if (o.get("canonical_name") or o.get("original_contract_text") or "").strip().lower() == "temporary works"
    ]
    assert len(tw_obligations) >= 1, "Temporary Works must appear in obligations_report."
    assert tw_obligations[0].get("evidenced_by_activities") is True, "Temporary Works must be evidenced when TW WBS present."


def test_c_programme_has_works_but_no_temporary_works_not_acceptable():
    """
    Test C: Programme has activities containing 'works' but no 'temporary works' in name or WBS.
    Result: NOT ACCEPTABLE. Fails if generic phrase matching is reintroduced for Temporary Works.
    """
    contract_data = _contract_data_with_temporary_works()
    p6_data = _p6_data_with_works_but_no_temporary_works()
    validator = ComprehensiveValidator()
    output = validator.validate(contract_data, p6_data)
    vs = output.get("validation_summary") or {}
    assert vs.get("acceptability_status") != "ACCEPTABLE", (
        "Programme with 'works' but no 'temporary works' must NOT be ACCEPTABLE (generic phrase match must not evidence Temporary Works)."
    )
    scope_cov = output.get("nec_alignment", {}).get("scope_coverage") or {}
    obligations_report = scope_cov.get("obligations_report") or []
    tw_obligations = [
        o for o in obligations_report
        if (o.get("canonical_name") or o.get("original_contract_text") or "").strip().lower() == "temporary works"
    ]
    assert len(tw_obligations) >= 1
    assert tw_obligations[0].get("evidenced_by_activities") is False, (
        "Temporary Works must not be evidenced when only generic 'works' appears (no 'temporary works' in name or WBS)."
    )


def _contract_data_with_tw_and_wbs_only_obligation():
    """Contract with Temporary Works (from frozen) plus one WBS_ONLY obligation 'Utilities Diversions' for generic evidence_mode tests."""
    contract_data = _contract_data_with_temporary_works()
    obligations = list((contract_data.get("obligation_entities") or {}).get("obligations") or [])
    obligations.append({
        "id": "OBL-WBS-001",
        "original_contract_text": "Utilities Diversions",
        "original_contract_texts": ["Utilities Diversions"],
        "canonical_name": "Utilities Diversions",
        "canonical_match_string": "utilities diversions",
        "clause_references": [],
        "facets": {"has_scope_component": True, "has_programme_duty": False, "has_governance_requirement": False, "has_timing_requirement": False},
        "mandatory_for_acceptance": True,
        "scope_classification": "ACTION_REQUIRED",
        "evidence_mode": EVIDENCE_MODE_WBS_ONLY,
    })
    contract_data["obligation_entities"] = {"obligations": obligations, "validation_error": None}
    return contract_data


def test_d_wbs_only_obligation_not_evidenced_by_phrase():
    """
    Generic evidence_mode test: an obligation with evidence_mode=WBS_ONLY must NOT be evidenced by phrase/token match.
    Programme has Temporary Works WBS (so TW evidenced) and 'Construction works' but NO 'Utilities Diversions' in name or WBS → Utilities Diversions not evidenced → NOT ACCEPTABLE.
    """
    contract_data = _contract_data_with_tw_and_wbs_only_obligation()
    p6_data = {
        "activities": [
            {"task_id": "1", "task_name": "Design", "wbs_id": "1"},
            {"task_id": "2", "task_name": "Construction works", "wbs_id": "2"},
            {"task_id": "3", "task_name": "TW activity", "wbs_id": "3"},
        ],
        "wbs": [
            {"wbs_id": "1", "parent_wbs_id": "", "wbs_name": "Design"},
            {"wbs_id": "2", "parent_wbs_id": "", "wbs_name": "Works"},
            {"wbs_id": "3", "parent_wbs_id": "", "wbs_name": "Temporary Works"},
        ],
        "calendars": [],
        "logic": [],
        "constraints": [],
        "metadata": {},
    }
    validator = ComprehensiveValidator()
    output = validator.validate(contract_data, p6_data)
    vs = output.get("validation_summary") or {}
    assert vs.get("acceptability_status") != "ACCEPTABLE", (
        "WBS_ONLY obligation must not be evidenced by phrase tokens; programme without 'Utilities Diversions' in name/WBS must NOT be ACCEPTABLE."
    )
    scope_cov = output.get("nec_alignment", {}).get("scope_coverage") or {}
    obligations_report = scope_cov.get("obligations_report") or []
    ud = [o for o in obligations_report if (o.get("original_contract_text") or "").strip() == "Utilities Diversions"]
    assert len(ud) == 1
    assert ud[0].get("evidenced_by_activities") is False, (
        "WBS_ONLY obligation must not be evidenced when only generic phrase tokens (e.g. 'works') appear in programme."
    )


def test_d_wbs_only_obligation_evidenced_by_wbs():
    """
    Generic evidence_mode test: WBS_ONLY obligation IS evidenced when obligation text appears in WBS path or activity name.
    """
    contract_data = _contract_data_with_tw_and_wbs_only_obligation()
    p6_data = {
        "activities": [
            {"task_id": "1", "task_name": "Design", "wbs_id": "1"},
            {"task_id": "2", "task_name": "TW activity", "wbs_id": "2"},
            {"task_id": "3", "task_name": "Diversion design", "wbs_id": "3"},
        ],
        "wbs": [
            {"wbs_id": "1", "parent_wbs_id": "", "wbs_name": "Design"},
            {"wbs_id": "2", "parent_wbs_id": "", "wbs_name": "Temporary Works"},
            {"wbs_id": "3", "parent_wbs_id": "", "wbs_name": "Utilities Diversions"},
        ],
        "calendars": [],
        "logic": [],
        "constraints": [],
        "metadata": {},
    }
    validator = ComprehensiveValidator()
    output = validator.validate(contract_data, p6_data)
    vs = output.get("validation_summary") or {}
    assert vs.get("acceptability_status") == "ACCEPTABLE", (
        "WBS_ONLY obligation must be ACCEPTABLE when programme has obligation text in WBS or activity name."
    )
    scope_cov = output.get("nec_alignment", {}).get("scope_coverage") or {}
    obligations_report = scope_cov.get("obligations_report") or []
    ud = [o for o in obligations_report if (o.get("original_contract_text") or "").strip() == "Utilities Diversions"]
    assert len(ud) == 1
    assert ud[0].get("evidenced_by_activities") is True
