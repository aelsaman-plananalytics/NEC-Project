"""
Regression tests: obligations are derived from contract extraction (no hardcoded obligations)
and "missing obligations" are detected from mandatory obligations that are not aligned.

Historically the system injected a hardcoded "Temporary Works" obligation; these tests ensure:
- We do NOT inject any obligations at build time.
- Mandatory obligations missing from the programme are surfaced via obligations_report and
  obligations_not_represented_but_mandatory (no special-case obligation names).
- evidence_mode=WBS_ONLY is enforced (name/WBS evidence only).
"""

import pytest

from app.p6_engine.frozen_requirements import build_frozen_requirements
from app.p6_engine.comprehensive_validator import ComprehensiveValidator
from app.p6_engine.obligation_entities import EVIDENCE_MODE_WBS_ONLY


def _contract_data_with_scope_obligation(
    text: str,
    *,
    mandatory_for_acceptance: bool = True,
    evidence_mode: str | None = None,
    canonical_match_string: str | None = None,
):
    contract_data = {
        "scope_items": [
            {
                "text": text,
                "mandatory_for_acceptance": mandatory_for_acceptance,
                **({"evidence_mode": evidence_mode} if evidence_mode else {}),
                **({"canonical_match_string": canonical_match_string} if canonical_match_string else {}),
            }
        ],
        "programme_compliance_model": {},
        "constraints": [],
    }
    frozen = build_frozen_requirements(contract_data)
    contract_data["obligation_entities"] = frozen["obligation_entities"]
    return contract_data


def _p6_data_without_obligation_text():
    """Programme with no activity whose name or WBS path contains the obligation text."""
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


def _p6_data_with_obligation_in_wbs(obligation_wbs_name: str):
    """Programme where obligation text appears in a WBS node name."""
    return {
        "activities": [
            {"task_id": "1", "task_name": "Design", "wbs_id": "1"},
            {"task_id": "2", "task_name": "Obligation activity", "wbs_id": "2"},
        ],
        "wbs": [
            {"wbs_id": "1", "parent_wbs_id": "", "wbs_name": "Design"},
            {"wbs_id": "2", "parent_wbs_id": "", "wbs_name": obligation_wbs_name},
        ],
        "calendars": [],
        "logic": [],
        "constraints": [],
        "metadata": {},
    }


def test_a_no_hardcoded_obligations_are_injected():
    contract_data = {"scope_items": [], "programme_compliance_model": {}, "constraints": []}
    frozen = build_frozen_requirements(contract_data)
    obligations = (frozen.get("obligation_entities") or {}).get("obligations") or []
    assert obligations == [], "No obligations should be injected when contract has none."


def test_b_missing_mandatory_obligation_is_reported_not_acceptable():
    contract_data = _contract_data_with_scope_obligation("Utilities Diversions", mandatory_for_acceptance=True)
    p6_data = _p6_data_without_obligation_text()
    validator = ComprehensiveValidator()
    output = validator.validate(contract_data, p6_data)

    vs = output.get("validation_summary") or {}
    assert vs.get("acceptability_status") != "ACCEPTABLE"

    scope_cov = output.get("nec_alignment", {}).get("scope_coverage") or {}
    obligations_report = scope_cov.get("obligations_report") or []
    not_rep = scope_cov.get("obligations_not_represented_but_mandatory") or []

    assert len(obligations_report) == 1
    assert obligations_report[0].get("mandatory_for_acceptance") is True
    assert obligations_report[0].get("aligned") is False
    assert obligations_report[0].get("not_represented_but_mandatory") is True
    assert len(not_rep) == 1


def _contract_data_with_wbs_only_obligation(text: str):
    return _contract_data_with_scope_obligation(
        text,
        mandatory_for_acceptance=True,
        evidence_mode=EVIDENCE_MODE_WBS_ONLY,
        canonical_match_string=text.lower(),
    )


def test_d_wbs_only_obligation_not_evidenced_by_phrase():
    """
    Generic evidence_mode test: an obligation with evidence_mode=WBS_ONLY must NOT be evidenced by phrase/token match.
    Programme has generic activities but NO obligation text in name/WBS → NOT ACCEPTABLE.
    """
    contract_data = _contract_data_with_wbs_only_obligation("Utilities Diversions")
    p6_data = _p6_data_without_obligation_text()
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
    contract_data = _contract_data_with_wbs_only_obligation("Utilities Diversions")
    p6_data = _p6_data_with_obligation_in_wbs("Utilities Diversions")
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
