"""
Contract obligation model for NEC programme validation.

Each real-world contract obligation MUST exist exactly ONCE.
Different clause perspectives (programme duty, governance, scope, timing) are FACETS
of the same obligation, not separate obligations. Evidence is evaluated ONCE per obligation.
"""

import re
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Facet flags (perspectives on the same obligation)
FACET_PROGRAMME_DUTY = "has_programme_duty"
FACET_GOVERNANCE = "has_governance_requirement"
FACET_SCOPE = "has_scope_component"
FACET_TIMING = "has_timing_requirement"

# Canonical key phrases: same underlying duty maps to same signature (order: longest first for match)
SIGNATURE_PHRASES = [
    "joint inspection",
    "completion documentation",
    "completion certificate",
    "bim transfer",
    "information transfer",
    "programme submission",
    "revised programme",
    "first programme",
    "site visit",
    "handover",
    "as-built",
    "as built",
    "acceptance certificate",
    "notice of completion",
    "early warning",
    "compensation event",
    "takeover",
    "inspection",
    "submission",
    "documentation",
    "transfer",
    "acceptance",
    "revision",
]

# Evidence mode: controls how programme activities evidence an obligation (single switch, no heuristics).
EVIDENCE_MODE_PHRASE = "PHRASE"       # Default: phrase/component matching.
EVIDENCE_MODE_WBS_ONLY = "WBS_ONLY"   # Evidence only if obligation text in activity name or WBS path (no phrase tokens).
EVIDENCE_MODE_HYBRID = "HYBRID"       # Phrase OR name/WBS match.

# Scope classification for evidence gate
SCOPE_CLASSIFICATION_ACTION_REQUIRED = "ACTION_REQUIRED"
SCOPE_CLASSIFICATION_ASSURANCE_REQUIRED = "ASSURANCE_REQUIRED"
ASSURANCE_INDICATOR_PATTERN = re.compile(
    r"\b(review|demonstrate|comply|governance|standard|assurance|professional\s+judgement|"
    r"inspection\s+of|quality\s+assurance|qa\s+review|compliance\s+check)\b",
    re.IGNORECASE
)

_STOPWORDS = {"the", "a", "an", "and", "or", "for", "with", "from", "by", "to", "shall", "must", "will", "may", "this", "that", "which", "such", "as", "on", "at", "in", "of"}


def _original_text_from_item(item: Any) -> str:
    """Extract verbatim contract text from an item."""
    if item is None:
        return ""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        t = (
            item.get("original_contract_text")
            or item.get("text")
            or item.get("value")
            or item.get("description")
            or item.get("name")
            or item.get("requirement")
            or item.get("content")
        )
        if t is None and isinstance(item.get("features"), dict):
            f = item["features"]
            t = f.get("description") or (isinstance(f.get("actions"), str) and f.get("actions")) or ""
            if not t and isinstance(f.get("assets"), list) and f["assets"]:
                t = " ".join(str(a) for a in f["assets"][:5])
        return (t if isinstance(t, str) else str(t or "")).strip()
    return str(item).strip()


def _clause_reference_from_item(item: Any) -> str:
    if isinstance(item, dict):
        return (item.get("clause_reference") or item.get("clause") or "").strip()
    return ""


def _obligation_signature(text: str) -> str:
    """
    Normalized action+object signature for deduplication.
    Same real-world duty => same signature. Used to merge programme/scope/governance/timing facets.
    """
    if not text or not text.strip():
        return ""
    lower = text.lower().strip()
    for phrase in SIGNATURE_PHRASES:
        if phrase in lower:
            return phrase
    words = [w for w in re.split(r"\W+", lower) if len(w) > 2 and w not in _STOPWORDS]
    return " ".join(sorted(set(words))[:6]) if words else lower[:80]


def classify_scope_obligation(text: str) -> str:
    """ACTION_REQUIRED vs ASSURANCE_REQUIRED for scope facet evidence gate."""
    if not text or not text.strip():
        return SCOPE_CLASSIFICATION_ACTION_REQUIRED
    return (
        SCOPE_CLASSIFICATION_ASSURANCE_REQUIRED
        if ASSURANCE_INDICATOR_PATTERN.search(text)
        else SCOPE_CLASSIFICATION_ACTION_REQUIRED
    )


def build_obligation_entities(contract_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a single deduplicated list of obligations. Multiple clauses referring to the same
    underlying duty are merged into ONE obligation with facets. Each obligation has one id (OBL-xxx),
    original_contract_text (list of clause texts), clause_references (list), facets (dict),
    mandatory_for_acceptance (true if ANY facet requires it).
    """
    # Collect raw (text, clause_ref, facet, mandatory, scope_classification?)
    raw: List[Tuple[str, str, str, bool, Optional[str]]] = []
    pcm = contract_data.get("programme_compliance_model") or {}

    def add(text: str, clause_ref: str, facet: str, mandatory: bool, scope_class: Optional[str] = None) -> None:
        if not text:
            return
        raw.append((text.strip(), clause_ref, facet, mandatory, scope_class))

    for item in (contract_data.get("scope_items") or []):
        text = _original_text_from_item(item)
        clause_ref = _clause_reference_from_item(item)
        classification = classify_scope_obligation(text)
        mandatory = bool(item.get("mandatory_for_acceptance")) if isinstance(item, dict) and "mandatory_for_acceptance" in item else (classification == SCOPE_CLASSIFICATION_ACTION_REQUIRED)
        add(text, clause_ref, FACET_SCOPE, mandatory, classification)

    raw_programme = (pcm.get("programme_duties") or pcm.get("required_activities") or contract_data.get("programme_requirements") or [])
    if isinstance(raw_programme, dict):
        raw_programme = list(raw_programme.values()) if raw_programme else []
    if not isinstance(raw_programme, list):
        raw_programme = [raw_programme] if raw_programme else []
    for item in raw_programme:
        text = _original_text_from_item(item)
        add(text, _clause_reference_from_item(item) or "Clause 32 / programme", FACET_PROGRAMME_DUTY, bool(item.get("mandatory_for_acceptance")) if isinstance(item, dict) and "mandatory_for_acceptance" in item else True, None)

    for item in list(contract_data.get("constraints") or []) + list(pcm.get("sequencing_and_timing_constraints") or []):
        text = _original_text_from_item(item)
        add(text, _clause_reference_from_item(item), FACET_TIMING, bool(item.get("mandatory_for_acceptance")) if isinstance(item, dict) and "mandatory_for_acceptance" in item else True, None)

    for item in (pcm.get("programme_governance_and_acceptance_rules") or []) + (pcm.get("completion_and_takeover_gates") or []):
        text = _original_text_from_item(item)
        add(text, _clause_reference_from_item(item), FACET_GOVERNANCE, bool(item.get("mandatory_for_acceptance")) if isinstance(item, dict) and "mandatory_for_acceptance" in item else True, None)

    # Ensure "Temporary Works" is always a mandatory scope obligation (NEC common requirement).
    # Without this, it only appears when the LLM (HybridAIExtractor) includes it in scope_items.
    tw_sig = _obligation_signature("Temporary Works")
    if not any(_obligation_signature(text) == tw_sig for text, _, _, _, _ in raw):
        add("Temporary Works", "", FACET_SCOPE, True, SCOPE_CLASSIFICATION_ACTION_REQUIRED)

    # Group by signature and merge
    by_signature: Dict[str, List[Tuple[str, str, str, bool, Optional[str]]]] = {}
    for text, clause_ref, facet, mandatory, scope_class in raw:
        sig = _obligation_signature(text)
        if not sig:
            continue
        if sig not in by_signature:
            by_signature[sig] = []
        by_signature[sig].append((text, clause_ref, facet, mandatory, scope_class))

    # Build one obligation per signature
    obligations: List[Dict[str, Any]] = []
    seen_signatures: List[str] = []
    for idx, (signature, group) in enumerate(sorted(by_signature.items(), key=lambda x: x[0])):
        texts = []
        clause_refs = []
        facets = {FACET_PROGRAMME_DUTY: False, FACET_GOVERNANCE: False, FACET_SCOPE: False, FACET_TIMING: False}
        mandatory = False
        scope_class = SCOPE_CLASSIFICATION_ACTION_REQUIRED
        for text, clause_ref, facet, mand, scope_class_item in group:
            if text and text not in texts:
                texts.append(text)
            if clause_ref and clause_ref not in clause_refs:
                clause_refs.append(clause_ref)
            facets[facet] = True
            mandatory = mandatory or mand
            if scope_class_item:
                scope_class = scope_class_item
        primary_text = texts[0] if texts else ""
        canonical_match_string = primary_text.strip().lower()
        ob_dict = {
            "id": f"OBL-{idx + 1:03d}",
            "original_contract_text": primary_text,
            "original_contract_texts": texts,
            "canonical_name": primary_text,
            "canonical_match_string": canonical_match_string,
            "clause_references": clause_refs,
            "facets": facets,
            "mandatory_for_acceptance": mandatory,
            "scope_classification": scope_class if facets.get(FACET_SCOPE) else None,
            "_signature": signature,
        }
        # WBS-critical obligations: evidence only from name/WBS substring (no phrase tokens).
        primary_lower = primary_text.strip().lower()
        if primary_lower == "temporary works":
            ob_dict["evidence_mode"] = EVIDENCE_MODE_WBS_ONLY
        elif primary_lower == "utilities diversions":
            ob_dict["evidence_mode"] = EVIDENCE_MODE_WBS_ONLY
        elif primary_lower == "traffic management":
            ob_dict["evidence_mode"] = EVIDENCE_MODE_WBS_ONLY
        obligations.append(ob_dict)
        seen_signatures.append(signature)

    # Safety assertion: no duplicate signatures (each signature appears once after merge)
    assert len(seen_signatures) == len(set(seen_signatures)), "Duplicate obligation signature after merge"

    return {
        "obligations": obligations,
        "obligation_entity_version": 3,
        "validation_error": None,
    }
