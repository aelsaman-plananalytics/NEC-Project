"""
Frozen contract obligations for NEC programme validation.

Each real-world obligation exists exactly ONCE. Different clause perspectives
(programme duty, governance, timing, scope) are facets of the same obligation.
Evidence is evaluated once per obligation; frozen list = single obligations list.
"""

from typing import Dict, List, Any

from app.p6_engine.obligation_entities import build_obligation_entities


def build_frozen_requirements(contract_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build deduplicated obligation entities from contract text.
    Single obligations list; frozen_requirements = same list for validators.
    """
    entities = build_obligation_entities(contract_data)
    obligations = entities.get("obligations") or []

    frozen_requirements: List[Dict[str, Any]] = []
    for ob in obligations:
        frozen_requirements.append({**ob})

    return {
        "obligation_entities": {
            "obligations": obligations,
            "validation_error": entities.get("validation_error"),
            "frozen_requirements_version": 7,
        },
        "frozen_requirements": frozen_requirements,
        "frozen_requirements_version": 7,
        "total_count": len(frozen_requirements),
        "obligation_entity_validation_error": entities.get("validation_error"),
    }
