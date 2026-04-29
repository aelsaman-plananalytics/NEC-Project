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
    # Raw items: (text, clause_ref, facet, mandatory, scope_class, evidence_mode_override, canonical_match_string_override, required_from_stage_override).
    # Overrides are set only at construction; validator must never infer from text.
    RawItem = Tuple[str, str, str, bool, Optional[str], Optional[str], Optional[str], Optional[str]]
    raw: List[RawItem] = []
    pcm = contract_data.get("programme_compliance_model") or {}

    def add(
        text: str,
        clause_ref: str,
        facet: str,
        mandatory: bool,
        scope_class: Optional[str] = None,
        evidence_mode_override: Optional[str] = None,
        canonical_match_string_override: Optional[str] = None,
        required_from_stage_override: Optional[str] = None,
    ) -> None:
        if not text:
            return
        raw.append((text.strip(), clause_ref, facet, mandatory, scope_class, evidence_mode_override, canonical_match_string_override, required_from_stage_override))

    for item in (contract_data.get("scope_items") or []):
        text = _original_text_from_item(item)
        clause_ref = _clause_reference_from_item(item)
        classification = classify_scope_obligation(text)
        mandatory = bool(item.get("mandatory_for_acceptance")) if isinstance(item, dict) and "mandatory_for_acceptance" in item else (classification == SCOPE_CLASSIFICATION_ACTION_REQUIRED)
        ev_mode = item.get("evidence_mode") if isinstance(item, dict) else None
        cms = item.get("canonical_match_string") if isinstance(item, dict) else None
        rfs = item.get("required_from_stage") if isinstance(item, dict) else None
        add(text, clause_ref, FACET_SCOPE, mandatory, classification, ev_mode, cms, rfs)

    raw_programme = (pcm.get("programme_duties") or pcm.get("required_activities") or contract_data.get("programme_requirements") or [])
    if isinstance(raw_programme, dict):
        raw_programme = list(raw_programme.values()) if raw_programme else []
    if not isinstance(raw_programme, list):
        raw_programme = [raw_programme] if raw_programme else []
    for item in raw_programme:
        text = _original_text_from_item(item)
        ev_mode = item.get("evidence_mode") if isinstance(item, dict) else None
        cms = item.get("canonical_match_string") if isinstance(item, dict) else None
        rfs = item.get("required_from_stage") if isinstance(item, dict) else None
        add(text, _clause_reference_from_item(item) or "Clause 32 / programme", FACET_PROGRAMME_DUTY, bool(item.get("mandatory_for_acceptance")) if isinstance(item, dict) and "mandatory_for_acceptance" in item else True, None, ev_mode, cms, rfs)

    for item in list(contract_data.get("constraints") or []) + list(pcm.get("sequencing_and_timing_constraints") or []):
        text = _original_text_from_item(item)
        add(
            text,
            _clause_reference_from_item(item),
            FACET_TIMING,
            bool(item.get("mandatory_for_acceptance")) if isinstance(item, dict) and "mandatory_for_acceptance" in item else False,
            None,
            None,
            None,
            None,
        )

    for item in (pcm.get("programme_governance_and_acceptance_rules") or []) + (pcm.get("completion_and_takeover_gates") or []):
        text = _original_text_from_item(item)
        add(
            text,
            _clause_reference_from_item(item),
            FACET_GOVERNANCE,
            bool(item.get("mandatory_for_acceptance")) if isinstance(item, dict) and "mandatory_for_acceptance" in item else False,
            None,
            None,
            None,
            None,
        )

    # Group by signature and merge
    by_signature: Dict[str, List[RawItem]] = {}
    for item in raw:
        text = item[0]
        sig = _obligation_signature(text)
        if not sig:
            continue
        if sig not in by_signature:
            by_signature[sig] = []
        by_signature[sig].append(item)

    # Build one obligation per signature. Each entity has explicit canonical_name, canonical_match_string, evidence_mode, mandatory_for_acceptance (read-only in validator).
    obligations: List[Dict[str, Any]] = []
    seen_signatures: List[str] = []
    for idx, (signature, group) in enumerate(sorted(by_signature.items(), key=lambda x: x[0])):
        texts = []
        clause_refs = []
        facets = {FACET_PROGRAMME_DUTY: False, FACET_GOVERNANCE: False, FACET_SCOPE: False, FACET_TIMING: False}
        mandatory = False
        scope_class = SCOPE_CLASSIFICATION_ACTION_REQUIRED
        evidence_mode_merged: Optional[str] = None
        canonical_match_string_merged: Optional[str] = None
        required_from_stage_merged: Optional[str] = None
        for text, clause_ref, facet, mand, scope_class_item, ev_override, cms_override, rfs_override in group:
            if text and text not in texts:
                texts.append(text)
            if clause_ref and clause_ref not in clause_refs:
                clause_refs.append(clause_ref)
            facets[facet] = True
            mandatory = mandatory or mand
            if scope_class_item:
                scope_class = scope_class_item
            if ev_override is not None and str(ev_override).strip():
                evidence_mode_merged = str(ev_override).strip().upper()
            if cms_override is not None and str(cms_override).strip():
                canonical_match_string_merged = str(cms_override).strip().lower()
            if rfs_override is not None and str(rfs_override).strip():
                required_from_stage_merged = str(rfs_override).strip().lower()
        primary_text = texts[0] if texts else ""
        canonical_match_string = canonical_match_string_merged if canonical_match_string_merged else primary_text.strip().lower()
        evidence_mode = evidence_mode_merged if evidence_mode_merged in (EVIDENCE_MODE_PHRASE, EVIDENCE_MODE_WBS_ONLY, EVIDENCE_MODE_HYBRID) else EVIDENCE_MODE_PHRASE
        ob_dict = {
            "id": f"OBL-{idx + 1:03d}",
            "original_contract_text": primary_text,
            "original_contract_texts": texts,
            "canonical_name": primary_text,
            "canonical_match_string": canonical_match_string,
            "evidence_mode": evidence_mode,
            "clause_references": clause_refs,
            "facets": facets,
            "mandatory_for_acceptance": mandatory,
            "scope_classification": scope_class if facets.get(FACET_SCOPE) else None,
            "_signature": signature,
        }
        if required_from_stage_merged is not None:
            ob_dict["required_from_stage"] = required_from_stage_merged
        obligations.append(ob_dict)
        seen_signatures.append(signature)

    # Safety assertion: no duplicate signatures (each signature appears once after merge)
    assert len(seen_signatures) == len(set(seen_signatures)), "Duplicate obligation signature after merge"

    return {
        "obligations": obligations,
        "obligation_entity_version": 3,
        "validation_error": None,
    }
