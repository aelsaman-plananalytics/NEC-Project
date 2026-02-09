"""
NEC validation importance tiers and outcome classification.

Used for accuracy, trust, and prioritisation: every check has exactly one tier
and one outcome. TIER_3 items have zero score impact; TIER_1 dominates.
"""

from typing import Dict, Any

# Importance tiers (what actually matters for programme acceptance)
TIER_1_CRITICAL = "TIER_1_CRITICAL"   # HARD_BREACH on failure; materially reduces score
TIER_2_SIGNIFICANT = "TIER_2_SIGNIFICANT"  # SOFT_BREACH on failure; influences score, does not auto-fail
TIER_3_INFORMATIONAL = "TIER_3_INFORMATIONAL"  # Reported as understood; MUST NOT affect score

# Outcome classification (defensible, NEC-meaningful)
COMPLIANT = "COMPLIANT"
HARD_BREACH = "HARD_BREACH"
SOFT_BREACH = "SOFT_BREACH"
INTERPRETIVE = "INTERPRETIVE"  # PM judgement required

# Mapping: alignment check key -> (importance_tier, source_clause, validation_basis)
ALIGNMENT_TRACEABILITY: Dict[str, Dict[str, Any]] = {
    "starting_date": {
        "importance_tier": TIER_1_CRITICAL,
        "source_clause": "Clause 31 / 3.1",
        "source_type": "explicit",
        "validation_basis": "date",
    },
    "completion_date": {
        "importance_tier": TIER_1_CRITICAL,
        "source_clause": "Clause 31 / 3.3",
        "source_type": "explicit",
        "validation_basis": "date",
    },
    "possession_dates": {
        "importance_tier": TIER_1_CRITICAL,
        "source_clause": "Clause 31 / 3.2",
        "source_type": "explicit",
        "validation_basis": "date",
    },
    "key_dates": {
        "importance_tier": TIER_2_SIGNIFICANT,
        "source_clause": "Contract key dates",
        "source_type": "inferred",
        "validation_basis": "existence",
    },
    "programme_submission": {
        "importance_tier": TIER_3_INFORMATIONAL,
        "source_clause": "Clause 32 / 3.5, 3.6",
        "source_type": "explicit",
        "validation_basis": "existence",
    },
    "delay_damages_alignment": {
        "importance_tier": TIER_2_SIGNIFICANT,
        "source_clause": "Clause 31 / 3.7",
        "source_type": "explicit",
        "validation_basis": "existence",
    },
    "weather_alignment": {
        "importance_tier": TIER_3_INFORMATIONAL,
        "source_clause": "Clause 6.1-6.3",
        "source_type": "explicit",
        "validation_basis": "existence",
    },
    "programme_compliance_model": {
        "importance_tier": TIER_1_CRITICAL,
        "source_clause": "Programme Compliance Model",
        "source_type": "explicit",
        "validation_basis": "logic",
    },
    "scope_coverage": {
        "importance_tier": TIER_1_CRITICAL,
        "source_clause": "Contract scope / works information",
        "source_type": "explicit",
        "validation_basis": "scope",
    },
}


def outcome_from_status(
    status: str,
    importance_tier: str,
    check_key: str = "",
) -> str:
    """
    Map alignment status to outcome (COMPLIANT, HARD_BREACH, SOFT_BREACH, INTERPRETIVE).
    TIER_1 failure -> HARD_BREACH; TIER_2 failure -> SOFT_BREACH; TIER_3 never affects outcome.
    """
    compliant_statuses = {
        "aligned", "match", "pass", "before", "present", "programme_earlier",
        "programme_missing",  # contract didn't require it
    }
    if status in compliant_statuses or status == "info" or status == "n/a":
        return COMPLIANT
    if importance_tier == TIER_3_INFORMATIONAL:
        return COMPLIANT  # TIER_3 reported but never breach
    if importance_tier == TIER_1_CRITICAL:
        if status in ("programme_later", "after", "fail", "contract_missing"):
            return HARD_BREACH
        if status == "programme_earlier":
            if check_key == "completion_date":
                return COMPLIANT  # programme finishes before contract = compliant
            if check_key == "possession_dates":
                return HARD_BREACH  # programme start < access date: HARD_BREACH
            return INTERPRETIVE
        if status in ("mismatch", "partial"):
            return SOFT_BREACH if status == "partial" else INTERPRETIVE
    if importance_tier == TIER_2_SIGNIFICANT:
        if status in ("fail", "programme_missing", "mismatch"):
            return SOFT_BREACH
        return INTERPRETIVE if status == "partial" else COMPLIANT
    return INTERPRETIVE


def attach_traceability(entry: Dict[str, Any], check_key: str) -> Dict[str, Any]:
    """Add source_clause, source_type, validation_basis, importance_tier, outcome to an alignment entry."""
    meta = ALIGNMENT_TRACEABILITY.get(check_key, {})
    tier = meta.get("importance_tier", TIER_2_SIGNIFICANT)
    entry["importance_tier"] = tier
    entry["source_clause"] = meta.get("source_clause", "")
    entry["source_type"] = meta.get("source_type", "inferred")
    entry["validation_basis"] = meta.get("validation_basis", "existence")
    status = entry.get("status", "unknown")
    entry["outcome"] = outcome_from_status(status, tier, check_key)
    return entry
