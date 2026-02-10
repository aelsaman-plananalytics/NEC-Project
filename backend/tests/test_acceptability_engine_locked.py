"""
Regression tests that lock the acceptability engine. See backend/ACCEPTABILITY_INVARIANT.md.

- Phrase pollution guard: WBS_ONLY must NOT be satisfied by "works", "temporary", or partial phrase matches.
- Obligation metadata integrity: WBS_ONLY without canonical_match_string or invalid evidence_mode must fail fast.
- Acceptability invariant: any mandatory unaligned → NOT ACCEPTABLE; no narrative or score may override.

These tests must fail if any future change breaks the invariant.
"""

import pytest

from app.p6_engine.comprehensive_validator import ComprehensiveValidator
from app.p6_engine.obligation_entities import EVIDENCE_MODE_WBS_ONLY, EVIDENCE_MODE_PHRASE


def _contract_temporary_works_mandatory():
    """Contract with only Temporary Works (mandatory, WBS_ONLY) — from frozen so it has canonical_match_string and evidence_mode at construction."""
    from app.p6_engine.frozen_requirements import build_frozen_requirements
    contract_data = {"scope_items": [], "programme_compliance_model": {}, "constraints": []}
    frozen = build_frozen_requirements(contract_data)
    contract_data["obligation_entities"] = frozen["obligation_entities"]
    return contract_data


def test_phrase_pollution_guard_wbs_only_not_satisfied_by_works_or_temporary():
    """
    WBS_ONLY obligation must NOT be satisfied by "works", "temporary", or partial phrase matches.
    Programme has activities with those words but NOT the full canonical_match_string in name or WBS → NOT ACCEPTABLE.
    """
    contract_data = _contract_temporary_works_mandatory()
    p6_data = {
        "activities": [
            {"task_id": "1", "task_name": "Construction works", "wbs_id": "1"},
            {"task_id": "2", "task_name": "Temporary fence", "wbs_id": "1"},
        ],
        "wbs": [{"wbs_id": "1", "parent_wbs_id": "", "wbs_name": "Works"}],
        "calendars": [],
        "logic": [],
        "constraints": [],
        "metadata": {},
    }
    validator = ComprehensiveValidator()
    output = validator.validate(contract_data, p6_data)
    vs = output.get("validation_summary") or {}
    assert vs.get("acceptability_status") != "ACCEPTABLE", (
        "WBS_ONLY (Temporary Works) must NOT be satisfied by 'works' or 'temporary' alone; only full 'temporary works' in name or WBS."
    )
    scope_cov = output.get("nec_alignment", {}).get("scope_coverage") or {}
    obligations_report = scope_cov.get("obligations_report") or []
    tw = next((o for o in obligations_report if (o.get("original_contract_text") or "").strip().lower() == "temporary works"), None)
    assert tw is not None and tw.get("evidenced_by_activities") is False


def test_obligation_metadata_integrity_wbs_only_without_canonical_match_string_fails():
    """WBS_ONLY obligation without canonical_match_string must raise RuntimeError (fail fast)."""
    from app.p6_engine.frozen_requirements import build_frozen_requirements
    base = build_frozen_requirements({"scope_items": [], "programme_compliance_model": {}, "constraints": []})
    obligations = list(base["obligation_entities"]["obligations"])
    obligations.append({
        "id": "OBL-BAD",
        "original_contract_text": "Some WBS obligation",
        "canonical_name": "Some WBS obligation",
        "clause_references": [],
        "facets": {"has_scope_component": True},
        "mandatory_for_acceptance": True,
        "evidence_mode": EVIDENCE_MODE_WBS_ONLY,
        # canonical_match_string deliberately missing
    })
    contract_data = {
        "obligation_entities": {"obligations": obligations, "validation_error": None},
        "scope_items": [],
        "programme_compliance_model": {},
        "constraints": [],
    }
    p6_data = {"activities": [{"task_id": "1", "task_name": "Design", "wbs_id": "1"}], "wbs": [{"wbs_id": "1", "parent_wbs_id": "", "wbs_name": "Design"}], "calendars": [], "logic": [], "constraints": [], "metadata": {}}
    validator = ComprehensiveValidator()
    with pytest.raises(RuntimeError) as exc_info:
        validator.validate(contract_data, p6_data)
    assert "canonical_match_string" in str(exc_info.value).lower() and "WBS_ONLY" in str(exc_info.value)


def test_obligation_metadata_integrity_invalid_evidence_mode_fails():
    """Invalid evidence_mode must raise RuntimeError (fail fast)."""
    from app.p6_engine.frozen_requirements import build_frozen_requirements
    base = build_frozen_requirements({"scope_items": [], "programme_compliance_model": {}, "constraints": []})
    obligations = list(base["obligation_entities"]["obligations"])
    obligations.append({
        "id": "OBL-BAD",
        "original_contract_text": "Something",
        "canonical_name": "Something",
        "canonical_match_string": "something",
        "clause_references": [],
        "facets": {"has_scope_component": True},
        "mandatory_for_acceptance": True,
        "evidence_mode": "INVALID_MODE",
    })
    contract_data = {
        "obligation_entities": {"obligations": obligations, "validation_error": None},
        "scope_items": [],
        "programme_compliance_model": {},
        "constraints": [],
    }
    p6_data = {"activities": [{"task_id": "1", "task_name": "Design", "wbs_id": "1"}], "wbs": [{"wbs_id": "1", "parent_wbs_id": "", "wbs_name": "Design"}], "calendars": [], "logic": [], "constraints": [], "metadata": {}}
    validator = ComprehensiveValidator()
    with pytest.raises(RuntimeError) as exc_info:
        validator.validate(contract_data, p6_data)
    assert "invalid evidence_mode" in str(exc_info.value).lower() or "allowed" in str(exc_info.value).lower()


def test_acceptability_invariant_mandatory_unaligned_implies_not_acceptable():
    """
    Any mandatory unaligned obligation → NOT ACCEPTABLE. No narrative or score may override.
    """
    contract_data = _contract_temporary_works_mandatory()
    p6_data = {
        "activities": [{"task_id": "1", "task_name": "Design", "wbs_id": "1"}],
        "wbs": [{"wbs_id": "1", "parent_wbs_id": "", "wbs_name": "Design"}],
        "calendars": [],
        "logic": [],
        "constraints": [],
        "metadata": {},
    }
    validator = ComprehensiveValidator()
    output = validator.validate(contract_data, p6_data)
    vs = output.get("validation_summary") or {}
    assert vs.get("acceptability_status") != "ACCEPTABLE"
    assert vs.get("overall_status") != "pass"
    failure_reasons = vs.get("acceptability_failure_reasons") or []
    assert any("temporary works" in r.lower() or "not represented" in r.lower() for r in failure_reasons)
