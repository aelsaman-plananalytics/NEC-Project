"""
Comprehensive Programme Validator.

Validates Primavera P6 programme against NEC contract with full clause extraction,
programme analysis, NEC alignment checks, risk assessment, and scoring.

Upgraded for: semantic compliance (not literal equality), importance tiers,
outcome classification (COMPLIANT/HARD_BREACH/SOFT_BREACH/INTERPRETIVE),
traceability (source_clause, source_type, validation_basis), and multi-dimension scoring.
TIER_3 (weather, payment, etc.) has zero score impact.
"""

import os
import re
import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
from app.p6_engine.xer_loader import XERLoader
from app.p6_engine.logic_checks import LogicChecker
from app.p6_engine.obligation_entities import (
    EVIDENCE_MODE_HYBRID,
    EVIDENCE_MODE_PHRASE,
    EVIDENCE_MODE_WBS_ONLY,
    SCOPE_CLASSIFICATION_ACTION_REQUIRED,
    SCOPE_CLASSIFICATION_ASSURANCE_REQUIRED,
)
# Programme obligations: activity must show explicit presence (submission, inspection, documentation)
_PROGRAMME_OBLIGATION_KEYWORDS = re.compile(
    r"\b(programme|submission|submit|inspection|inspect|completion\s+documentation|"
    r"certificate|handover|bim|transfer|acceptance|notice|revision|revised)\b",
    re.IGNORECASE
)
_GENERIC_VERB_ONLY = re.compile(
    r"^\s*(provide|maintain|ensure|deliver|supply|support)\s+(the|a|an)?\s*$",
    re.IGNORECASE
)

# Generic activity types that are NOT valid evidence for ACTION_REQUIRED scope unless scope explicitly requires them
_GENERIC_EVIDENCE_PATTERNS = [
    re.compile(r"\binspection\b", re.IGNORECASE),
    re.compile(r"\bmilestone\b", re.IGNORECASE),
    re.compile(r"\bcompletion\s+documentation\b", re.IGNORECASE),
    re.compile(r"\bcompletion\s+certificate\b", re.IGNORECASE),
    re.compile(r"\bgovernance\s+review\b", re.IGNORECASE),
    re.compile(r"\bgovernance\b.*\b(review|meeting)\b", re.IGNORECASE),
    re.compile(r"\breview\s+(only|meeting|point)\b", re.IGNORECASE),
    re.compile(r"^\s*(inspection|review|milestone)\s*$", re.IGNORECASE),
]
from app.p6_engine.validation_tiers import (
    TIER_1_CRITICAL,
    TIER_2_SIGNIFICANT,
    TIER_3_INFORMATIONAL,
    COMPLIANT,
    HARD_BREACH,
    SOFT_BREACH,
    INTERPRETIVE,
    attach_traceability,
)


_SEMANTIC_ACTION_CANONICAL_MAP = {
    "construct": "construct",
    "construction": "construct",
    "constructing": "construct",
    "constructs": "construct",
    "build": "construct",
    "building": "construct",
    "builds": "construct",
    "erect": "construct",
    "erecting": "construct",
    "carryout": "construct",
    "deliver": "construct",
    "delivery": "construct",
    "execute": "construct",
    "executing": "construct",
    "install": "install",
    "installing": "install",
    "installation": "install",
    "installations": "install",
    "fit": "install",
    "fitting": "install",
    "fix": "install",
    "commission": "commission",
    "commissioning": "commission",
    "commissioned": "commission",
    "test": "commission",
    "testing": "commission",
    "design": "design",
    "designing": "design",
    "engineer": "design",
    "engineering": "design",
    "prepare": "prepare",
    "preparation": "prepare",
    "produce": "prepare",
    "producing": "prepare",
    "complete": "complete",
    "completing": "complete",
    "completion": "complete",
    "submit": "submit",
    "submission": "submit",
    "submitting": "submit",
    "provide": "provide",
    "providing": "provide",
    "transfer": "transfer",
    "transferring": "transfer",
    "handover": "transfer",
    "hand": "transfer",
    "survey": "survey",
    "surveying": "survey",
    "investigate": "survey",
    "investigation": "survey",
    "investigations": "survey",
    "inspect": "inspect",
    "inspection": "inspect",
    "review": "inspect",
    "check": "inspect",
    "maintain": "maintain",
    "maintenance": "maintain",
    "monitor": "monitor",
    "monitoring": "monitor",
    "manage": "manage",
    "management": "manage",
}

_SEMANTIC_NOUN_CANONICAL_MAP = {
    "asset": "asset",
    "assets": "asset",
    "work": "asset",
    "works": "asset",
    "scheme": "asset",
    "structure": "asset",
    "structures": "asset",
    "main": "asset",
    "section": "section",
    "sections": "section",
    "piling": "piling",
    "pile": "piling",
    "piles": "piling",
    "wall": "wall",
    "walls": "wall",
    "commissioning": "commissioning",
    "commission": "commissioning",
    "testing": "commissioning",
    "test": "commissioning",
    "survey": "survey",
    "surveys": "survey",
    "investigation": "survey",
    "investigations": "survey",
    "inspection": "inspection",
    "inspections": "inspection",
    "documentation": "documentation",
    "documents": "documentation",
    "records": "documentation",
    "deliverables": "documentation",
    "handover": "handover",
    "hand": "handover",
    "transfer": "handover",
    "takeover": "handover",
    "database": "bim",
    "databases": "bim",
    "model": "bim",
    "models": "bim",
    "bim": "bim",
    "information": "bim",
    "data": "bim",
    "calendar": "calendar",
    "calendars": "calendar",
    "programme": "programme",
    "program": "programme",
    "risk": "risk",
    "risks": "risk",
    "gate": "gate",
    "gates": "gate",
}

_SEMANTIC_STOP_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "into",
    "onto",
    "that",
    "this",
    "these",
    "those",
    "of",
    "to",
    "by",
    "on",
    "in",
    "an",
    "a",
    "at",
    "any",
    "all",
    "shall",
    "must",
    "will",
    "should",
    "include",
    "including",
    "ensure",
    "ensuring",
    "site",
    "project",
    "programme",
    "program",
}


def _normalize_token(token: str) -> str:
    cleaned = re.sub(r"[^a-z]", "", token.lower())
    if len(cleaned) <= 2:
        return ""
    if cleaned.endswith(("ing", "ers", "ies")) and len(cleaned) > 5:
        if cleaned.endswith("ing"):
            cleaned = cleaned[:-3]
        elif cleaned.endswith("ers"):
            cleaned = cleaned[:-2]
        elif cleaned.endswith("ies"):
            cleaned = cleaned[:-3] + "y"
    elif cleaned.endswith(("ed", "es", "s")) and len(cleaned) > 4:
        if cleaned.endswith("ed") or cleaned.endswith("es"):
            cleaned = cleaned[:-2]
        else:
            cleaned = cleaned[:-1]
    return cleaned


def _canonical_action(token: str) -> Optional[str]:
    if not token:
        return None
    if token in _SEMANTIC_ACTION_CANONICAL_MAP:
        return _SEMANTIC_ACTION_CANONICAL_MAP[token]
    return _SEMANTIC_ACTION_CANONICAL_MAP.get(_normalize_token(token))


def _canonical_noun(token: str) -> Optional[str]:
    if not token:
        return None
    if token in _SEMANTIC_NOUN_CANONICAL_MAP:
        return _SEMANTIC_NOUN_CANONICAL_MAP[token]
    return _SEMANTIC_NOUN_CANONICAL_MAP.get(_normalize_token(token))


def _extract_semantic_intent(text: str) -> Dict[str, Set[str]]:
    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    actions: Set[str] = set()
    nouns: Set[str] = set()
    raw_tokens: Set[str] = set()
    for tok in tokens:
        normalized = _normalize_token(tok)
        if not normalized or normalized in _SEMANTIC_STOP_WORDS:
            continue
        raw_tokens.add(normalized)
        canonical_action = _canonical_action(normalized)
        if canonical_action:
            actions.add(canonical_action)
            continue
        canonical_noun = _canonical_noun(normalized)
        if canonical_noun:
            nouns.add(canonical_noun)
        else:
            nouns.add(normalized)
    if not nouns and raw_tokens:
        nouns = set(raw_tokens)
    return {"actions": actions, "nouns": nouns, "raw_tokens": raw_tokens}


def _semantic_intent_match(required_intent: Dict[str, Set[str]], programme_intent: Dict[str, Set[str]]) -> bool:
    required_actions = required_intent.get("actions", set())
    required_nouns = required_intent.get("nouns", set())
    programme_actions = programme_intent.get("actions", set())
    programme_nouns = programme_intent.get("nouns", set())

    actions_ok = not required_actions or bool(required_actions & programme_actions)
    if not actions_ok:
        return False

    if not required_nouns:
        return True

    if programme_nouns & required_nouns:
        return True

    # Allow general asset nouns to match broader construction activities
    if required_nouns <= {"asset"} and programme_actions:
        return True

    if required_intent.get("raw_tokens", set()) & programme_intent.get("raw_tokens", set()):
        return True

    return False


def _build_missing_reason(required_intent: Dict[str, Set[str]]) -> str:
    parts: List[str] = []
    actions = sorted(required_intent.get("actions", set()))
    nouns = sorted(required_intent.get("nouns", set()))
    if actions:
        parts.append(f"verb intent: {', '.join(actions)}")
    if nouns:
        parts.append(f"noun intent: {', '.join(nouns)}")
    detail = "; ".join(parts)
    base_reason = "Required programme activities missing"
    if detail:
        return f"{base_reason} ({detail})"
    return base_reason


_DESIGN_STAGE_KEYWORDS = [
    "design",
    "designer",
    "design review",
    "design development",
    "drawing",
    "drawings",
    "ifc",
    "information model",
    "bim",
    "model",
    "models",
    "technical submission",
    "approval",
    "approve",
    "accepted design",
    "design coordination",
]

_CONSTRUCTION_STAGE_KEYWORDS = [
    "construct",
    "construction",
    "build",
    "installation",
    "install",
    "excavate",
    "earthworks",
    "piling",
    "pile",
    "foundation",
    "concrete",
    "pour",
    "reinforcement",
    "steelwork",
    "structure",
    "wall",
    "deck",
    "erection",
    "fabrication",
    "fit-out",
    "roads",
    "utilities",
    "diversion",
    "temporary works",
    "mobilisation",
    "site setup",
]

_COMMISSIONING_KEYWORDS = [
    "commission",
    "commissioning",
    "test",
    "testing",
    "pre-commission",
    "start-up",
    "handover",
    "takeover",
    "client training",
    "performance test",
]

_REVISION_STAGE_KEYWORDS = [
    "rebaseline",
    "re-baseline",
    "revision",
    "revised",
    "update",
    "updated programme",
    "programme update",
    "mitigation",
    "acceleration",
    "change impact",
    "remedial",
    "variation",
    "delta",
    "reforecast",
]

_GOVERNANCE_KEYWORDS = [
    "submit programme",
    "first programme",
    "programme submission",
    "programme accept",
    "clause 31",
    "acceptance",
    "progress meeting",
    "reporting",
    "information delivery",
    "information exchange",
    "weekly report",
    "monthly report",
]

_STAGE_TITLES = {
    "DESIGN_STAGE": "Design Stage",
    "CONSTRUCTION_STAGE": "Construction Stage",
    "REVISED_CONSTRUCTION_STAGE": "Revised Construction Stage",
}

_DESIGN_CONTRACT_TOKENS = [
    "cdt",
    "ese",
    "appraisal",
    "psc",
    "professional service",
    "professional-services",
    "design contract",
    "consultancy",
    "engineering services",
    "design services",
]

_CONSTRUCTION_CONTRACT_TOKENS = [
    "ecc",
    "works",
    "construction",
    "option a",
    "option b",
    "option c",
    "option d",
    "option e",
    "option f",
    "engineering and construction",
    "contractor",
    "design and build",
]

_SCOPE_KEYS = (
    "scope_summary",
    "scope_of_work",
    "scope",
    "work_description",
    "works_information",
    "project_description",
    "project_scope",
    "scope_text",
    "scope_details",
)


def _detect_keywords(text: str, keywords: List[str]) -> List[str]:
    hits: List[str] = []
    lowered = text.lower()
    for keyword in keywords:
        if keyword in lowered:
            hits.append(keyword)
    return hits


def _truncate_evidence(evidence: List[str], limit: int = 5) -> List[str]:
    if len(evidence) <= limit:
        return evidence
    return evidence[:limit] + [f"... (+{len(evidence) - limit} more)"]


def _determine_programme_stage(
    contract_data: Dict[str, Any],
    programme_summary: Dict[str, Any],
    activities: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Determine programme stage using hierarchical signals with explicit reasoning."""
    signals_detail: Dict[str, Any] = {
        "contract_type": {"values": [], "decision": None},
        "scope": {},
        "structure": {},
        "keywords": {},
    }
    signals_used: List[str] = []
    signals_ignored: List[str] = []
    reasoning_parts: List[str] = []

    # ------------------------------------------------------------------
    # Step 1: Contract type (strongest signal)
    # ------------------------------------------------------------------
    contract_type_values: List[str] = []
    contract_type_raw = contract_data.get("contract_type")
    if isinstance(contract_type_raw, str) and contract_type_raw.strip():
        contract_type_values.append(contract_type_raw.strip())
    project_info = contract_data.get("project", {})
    if isinstance(project_info, dict):
        for key in ("contract_type", "type"):
            val = project_info.get(key)
            if isinstance(val, str) and val.strip():
                contract_type_values.append(val.strip())
    signals_detail["contract_type"]["values"] = contract_type_values

    contract_stage = None
    contract_stage_source = ""
    for value in contract_type_values:
        lower = value.lower()
        if any(token in lower for token in _DESIGN_CONTRACT_TOKENS):
            contract_stage = "DESIGN_STAGE"
            contract_stage_source = value
            break
        if any(token in lower for token in _CONSTRUCTION_CONTRACT_TOKENS):
            contract_stage = "CONSTRUCTION_STAGE"
            contract_stage_source = value
            break

    stage: Optional[str] = None
    if contract_stage:
        stage = contract_stage
        signals_detail["contract_type"]["decision"] = contract_stage
        msg = f"Contract type '{contract_stage_source}' classified as {_STAGE_TITLES.get(contract_stage, contract_stage)}."
        signals_used.append(msg)
        reasoning_parts.append(msg)
    else:
        if contract_type_values:
            signals_ignored.append("Contract type provided but not recognised as design or works; moving to scope analysis.")
        else:
            signals_ignored.append("No explicit contract type provided; moving to scope analysis.")

    # ------------------------------------------------------------------
    # Step 2: Scope language (second strongest)
    # ------------------------------------------------------------------
    scope_texts: List[str] = []
    for key in _SCOPE_KEYS:
        val = contract_data.get(key)
        if isinstance(val, str) and val.strip():
            scope_texts.append(val)
    project_scope = project_info.get("scope") if isinstance(project_info, dict) else None
    if isinstance(project_scope, str) and project_scope.strip():
        scope_texts.append(project_scope)

    pcm = contract_data.get("programme_compliance_model", {})
    if isinstance(pcm, dict):
        scope_annex = pcm.get("scope_summary")
        if isinstance(scope_annex, str) and scope_annex.strip():
            scope_texts.append(scope_annex)

    scope_design_examples: List[str] = []
    scope_construction_examples: List[str] = []
    scope_revision_examples: List[str] = []
    for text in scope_texts:
        tokens = _classify_requirement_tokens(text)
        snippet = text[:140].strip()
        if tokens["design"] > 0 and (tokens["construction"] + tokens["commissioning"]) == 0:
            scope_design_examples.append(snippet)
        if tokens["construction"] + tokens["commissioning"] > 0 and tokens["design"] == 0:
            scope_construction_examples.append(snippet)
        if tokens["revision"] > 0:
            scope_revision_examples.append(snippet)
    signals_detail["scope"] = {
        "design_examples": _truncate_evidence(scope_design_examples),
        "construction_examples": _truncate_evidence(scope_construction_examples),
        "revision_examples": _truncate_evidence(scope_revision_examples),
    }

    if stage is None:
        if scope_design_examples and not scope_construction_examples:
            stage = "DESIGN_STAGE"
            msg = "Scope language describes design-only obligations; selecting Design Stage."
            signals_used.append(msg)
            reasoning_parts.append(msg)
        elif scope_construction_examples and not scope_design_examples:
            stage = "CONSTRUCTION_STAGE"
            msg = "Scope language describes physical works obligations; selecting Construction Stage."
            signals_used.append(msg)
            reasoning_parts.append(msg)
        elif scope_design_examples or scope_construction_examples:
            signals_ignored.append("Scope language references both design and construction; no definitive stage from scope alone.")
    else:
        if stage == "DESIGN_STAGE":
            if scope_design_examples:
                signals_used.append("Scope language aligns with Design Stage.")
            if scope_construction_examples:
                signals_ignored.append("Scope references construction but contract type precedence applies.")
        else:
            if scope_construction_examples:
                signals_used.append("Scope language aligns with Construction Stage.")
            if scope_design_examples:
                signals_ignored.append("Scope references design but higher-priority contract type indicates construction.")

    # ------------------------------------------------------------------
    # Step 3: Programme structure (dominance of activities)
    # ------------------------------------------------------------------
    structure_design_examples: List[str] = []
    structure_construction_examples: List[str] = []
    structure_revision_examples: List[str] = []
    for act in activities:
        name = (act.get("name") or "").strip()
        if not name:
            continue
        tokens = _classify_requirement_tokens(name)
        if tokens["design"] > (tokens["construction"] + tokens["commissioning"]) and tokens["design"] > 0:
            structure_design_examples.append(name)
        if tokens["construction"] + tokens["commissioning"] > 0 and tokens["design"] == 0:
            structure_construction_examples.append(name)
        if tokens["revision"] > 0:
            structure_revision_examples.append(name)
    signals_detail["structure"] = {
        "design_activities": _truncate_evidence(structure_design_examples),
        "construction_activities": _truncate_evidence(structure_construction_examples),
        "revision_activities": _truncate_evidence(structure_revision_examples),
    }

    if stage is None:
        if len(structure_design_examples) >= max(3, len(structure_construction_examples) * 2) and len(structure_construction_examples) <= 1:
            stage = "DESIGN_STAGE"
            msg = "Programme activities are dominated by design tasks; selecting Design Stage."
            signals_used.append(msg)
            reasoning_parts.append(msg)
        elif len(structure_construction_examples) >= max(3, len(structure_design_examples) * 2):
            stage = "CONSTRUCTION_STAGE"
            msg = "Programme activities are dominated by physical works; selecting Construction Stage."
            signals_used.append(msg)
            reasoning_parts.append(msg)
        elif structure_design_examples or structure_construction_examples:
            signals_ignored.append("Programme activities include both design and works; structure alone not decisive.")
    else:
        if stage == "DESIGN_STAGE":
            if structure_design_examples:
                signals_used.append("Programme structure supports Design Stage (design tasks dominant).")
            if structure_construction_examples:
                signals_ignored.append("Programme includes construction tasks but higher-priority signals keep Design Stage.")
        else:
            if structure_construction_examples:
                signals_used.append("Programme structure supports Construction Stage (works tasks dominant).")
            if structure_design_examples:
                signals_ignored.append("Programme includes design tasks but higher-priority signals keep Construction Stage.")

    # ------------------------------------------------------------------
    # Step 4: Keywords / metadata (weakest signal)
    # ------------------------------------------------------------------
    keyword_design_examples: List[str] = []
    keyword_construction_examples: List[str] = []
    keyword_revision_examples: List[str] = []

    metadata = programme_summary.get("metadata", {})
    if isinstance(metadata, dict):
        for key in ("programme_name", "programme_stage", "programme_type", "update_type", "notes"):
            val = metadata.get(key)
            if isinstance(val, str) and val.strip():
                lowered = val.lower()
                if _detect_keywords(lowered, _DESIGN_STAGE_KEYWORDS):
                    keyword_design_examples.append(f'{key}: {val}')
                if _detect_keywords(lowered, _CONSTRUCTION_STAGE_KEYWORDS) or _detect_keywords(lowered, _COMMISSIONING_KEYWORDS):
                    keyword_construction_examples.append(f'{key}: {val}')
                if _detect_keywords(lowered, _REVISION_STAGE_KEYWORDS):
                    keyword_revision_examples.append(f'{key}: {val}')

    if isinstance(pcm, dict):
        revision_note = pcm.get("revision_notes")
        if isinstance(revision_note, str) and revision_note.strip():
            if _detect_keywords(revision_note.lower(), _REVISION_STAGE_KEYWORDS):
                keyword_revision_examples.append(f'PCM revision_notes: {revision_note}')

    signals_detail["keywords"] = {
        "design_terms": _truncate_evidence(keyword_design_examples),
        "construction_terms": _truncate_evidence(keyword_construction_examples),
        "revision_terms": _truncate_evidence(keyword_revision_examples),
    }

    if stage is None:
        if keyword_design_examples and not keyword_construction_examples:
            stage = "DESIGN_STAGE"
            msg = "Metadata keywords indicate design-stage programme."
            signals_used.append(msg)
            reasoning_parts.append(msg)
        elif keyword_construction_examples and not keyword_design_examples:
            stage = "CONSTRUCTION_STAGE"
            msg = "Metadata keywords indicate construction-stage programme."
            signals_used.append(msg)
            reasoning_parts.append(msg)

    # ------------------------------------------------------------------
    # Final fallback and revision logic
    # ------------------------------------------------------------------
    if stage is None:
        stage = "CONSTRUCTION_STAGE"
        msg = "No decisive signals detected; defaulting to Construction Stage per NEC guidance."
        signals_used.append(msg)
        reasoning_parts.append(msg)

    total_revision_hits = (
        len(scope_revision_examples)
        + len(structure_revision_examples)
        + len(keyword_revision_examples)
    )
    if stage == "CONSTRUCTION_STAGE" and total_revision_hits >= 2 and len(structure_construction_examples) >= 3:
        stage = "REVISED_CONSTRUCTION_STAGE"
        msg = "Revision indicators present alongside live works; classifying as Revised Construction Stage."
        signals_used.append(msg)
        reasoning_parts.append(msg)

    if stage == "DESIGN_STAGE":
        excluded = {
            "CONSTRUCTION_STAGE": "Higher-priority signals (contract/scope) emphasise design rather than physical works.",
            "REVISED_CONSTRUCTION_STAGE": "No revision evidence alongside design-led obligations.",
        }
    elif stage == "REVISED_CONSTRUCTION_STAGE":
        excluded = {
            "DESIGN_STAGE": "Programme contains active works and revision impacts; not a pure design phase.",
            "CONSTRUCTION_STAGE": "Revision signals require acknowledgement of programme changes.",
        }
    else:
        excluded = {
            "DESIGN_STAGE": "Design indicators were outweighed by works obligations and programme structure.",
            "REVISED_CONSTRUCTION_STAGE": "Revision evidence was insufficient to reclassify construction stage.",
        }

    reasoning = " ".join(reasoning_parts).strip()
    if not reasoning:
        reasoning = f"Classified as {_STAGE_TITLES.get(stage, stage)} based on available signals."

    return {
        "stage": stage,
        "stage_label": _STAGE_TITLES.get(stage, stage),
        "signals": signals_detail,
        "signals_used": signals_used,
        "signals_ignored": signals_ignored,
        "reasoning": reasoning,
        "excluded": excluded,
    }


def _classify_requirement_tokens(requirement_text: str) -> Dict[str, int]:
    lowered = requirement_text.lower()
    return {
        "design": len(_detect_keywords(lowered, _DESIGN_STAGE_KEYWORDS)),
        "construction": len(_detect_keywords(lowered, _CONSTRUCTION_STAGE_KEYWORDS)),
        "commissioning": len(_detect_keywords(lowered, _COMMISSIONING_KEYWORDS)),
        "revision": len(_detect_keywords(lowered, _REVISION_STAGE_KEYWORDS)),
        "governance": len(_detect_keywords(lowered, _GOVERNANCE_KEYWORDS)),
    }


def _canonical_required_activity_key(text: str) -> str:
    """Produce a canonical key for deduplication: normalized, collapsed whitespace, lower."""
    if not text or not isinstance(text, str):
        return ""
    return " ".join(text.lower().strip().split())


def _deduplicate_required_activities(applicable: List[Any]) -> List[str]:
    """Deduplicate by canonical key; return ordered list of unique requirement strings (first occurrence kept)."""
    seen: Dict[str, str] = {}
    out: List[str] = []
    for req in applicable:
        text = req if isinstance(req, str) else str(req)
        if not text.strip():
            continue
        key = _canonical_required_activity_key(text)
        if not key:
            continue
        if key in seen:
            continue
        seen[key] = text
        out.append(text)
    return out


def _determine_contract_context(
    contract_data: Dict[str, Any],
    programme_summary: Dict[str, Any],
) -> Dict[str, str]:
    """Freeze high-level context once for the entire validation."""
    contract_type = ""
    contract_type_candidates: List[str] = []
    project_info = contract_data.get("project", {})
    for key in ("contract_type", "type"):
        val = contract_data.get(key) or (project_info.get(key) if isinstance(project_info, dict) else None)
        if isinstance(val, str) and val.strip():
            contract_type_candidates.append(val.strip())
    if contract_type_candidates:
        contract_type = contract_type_candidates[0]
    else:
        contract_type = "UNKNOWN"

    # Programme intent: design-led vs construction-led vs mixed (supporting signal only)
    design_hits = 0
    construction_hits = 0
    activities = programme_summary.get("activities", [])
    for act in activities:
        name = (act.get("name") or "").strip().lower()
        if not name:
            continue
        if _detect_keywords(name, _DESIGN_STAGE_KEYWORDS):
            design_hits += 1
        if _detect_keywords(name, _CONSTRUCTION_STAGE_KEYWORDS) or _detect_keywords(name, _COMMISSIONING_KEYWORDS):
            construction_hits += 1
    if design_hits > construction_hits * 1.5 and design_hits >= 2:
        programme_intent = "design-led"
    elif construction_hits > design_hits * 1.5 and construction_hits >= 2:
        programme_intent = "construction-led"
    else:
        programme_intent = "mixed"

    return {
        "contract_type": contract_type,
        "programme_intent": programme_intent,
    }


EXPECTED_NOW = "EXPECTED_NOW"
EXPECTED_LATER = "EXPECTED_LATER"


def _assign_expectation_flags(contract_required_activities: List[str], stage: str) -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []
    for requirement_text in contract_required_activities:
        tokens = _classify_requirement_tokens(requirement_text)
        if stage == "DESIGN_STAGE":
            if tokens["design"] > 0 or tokens["governance"] > 0:
                expectation = EXPECTED_NOW
                reason = "Design/governance obligation expected in current (design) stage."
            else:
                expectation = EXPECTED_LATER
                reason = "Physical works obligation scheduled for later stage."
        elif stage == "CONSTRUCTION_STAGE":
            if tokens["construction"] > 0 or tokens["commissioning"] > 0 or tokens["governance"] > 0:
                expectation = EXPECTED_NOW
                reason = "Construction/commissioning/governance obligation expected during live works."
            else:
                expectation = EXPECTED_LATER
                reason = "Design-focused obligation permitted later in the lifecycle."
        elif stage == "REVISED_CONSTRUCTION_STAGE":
            if tokens["construction"] > 0 or tokens["commissioning"] > 0 or tokens["governance"] > 0 or tokens["revision"] > 0:
                expectation = EXPECTED_NOW
                reason = "Live works or revision obligation required in current revised stage."
            else:
                expectation = EXPECTED_LATER
                reason = "Design-focused obligation allowed to complete after revisions."
        else:
            expectation = EXPECTED_NOW
            reason = "Stage unknown; conservatively treating as required now."
        entries.append({
            "requirement": requirement_text,
            "expectation": expectation,
            "expectation_reason": reason,
        })
    return entries


def _expectation_policy_for_stage(stage: str) -> str:
    if stage == "DESIGN_STAGE":
        return "Design stage: design and governance obligations are required now; construction activities may be completed later."
    if stage == "REVISED_CONSTRUCTION_STAGE":
        return "Revised construction stage: construction, commissioning, governance, and revision obligations are required now; purely design activities may complete later."
    if stage == "CONSTRUCTION_STAGE":
        return "Construction stage: construction, commissioning, and governance obligations are required now; design-only activities may complete later."
    return "Stage unknown; treating all obligations as required now for safety."


def _is_advisory_design_text(text: str) -> bool:
    """True if obligation text suggests advisory/design/professional judgement (NEC: assurance-based alignment sufficient)."""
    if not text or not text.strip():
        return False
    lower = text.strip().lower()
    return bool(
        re.search(
            r"\b(advice|advisory|design|professional\s+judgement|judgment|consider|inform|review|"
            r"consult|demonstrate\s+compliance|governance|standard|assurance|comply)\b",
            lower,
        )
    )


def _is_advisory_governance_coordination_text(text: str) -> bool:
    """True if obligation is advisory, design-led, governance, coordination, or professional-judgement based (ESE/appraisal: default assurance_based)."""
    if not text or not text.strip():
        return False
    lower = text.strip().lower()
    return bool(
        re.search(
            r"\b(advice|advisory|design|professional\s+judgement|judgment|consider|inform|review|"
            r"consult|governance|standard|assurance|comply|coordinate|liaise|engage|discuss|"
            r"buildability|construction\s+method|utility\s+compan|diversion)\b",
            lower,
        )
    )


def _is_ese_assurance_obligation(primary_text: str, facets: Dict[str, Any]) -> bool:
    """True if obligation is governance, advisory, register-based, or engagement (satisfied by assurance when stage is ESE/appraisal)."""
    if facets.get("has_governance_requirement"):
        return True
    if not primary_text or not primary_text.strip():
        return False
    lower = primary_text.strip().lower()
    if _is_advisory_governance_coordination_text(primary_text):
        return True
    if "register" in lower or "engagement" in lower or " engage " in lower:
        return True
    return False


class ComprehensiveValidator:
    """
    Comprehensive validation engine for NEC-P6 alignment.
    """
    
    def __init__(self):
        """Initialize comprehensive validator."""
        self.xer_loader = XERLoader()
        self.logic_checker = LogicChecker()
    
    def validate(
        self,
        contract_data: Dict[str, Any],
        p6_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Perform comprehensive validation.
        
        Args:
            contract_data: Contract JSON from analyze_contract
            p6_data: P6 programme data from XERLoader
            
        Returns:
            Complete validation output with all sections
        """
        # ACCEPTABILITY INVARIANT (backend/ACCEPTABILITY_INVARIANT.md): When obligation_entities_used, only obligation alignment may set pass/ACCEPTABLE. No legacy engines, no scores, no report-layer inference.
        # Hard-disable legacy engines before any alignment runs.
        obligation_entities = contract_data.get("obligation_entities") or {}
        obligation_entities_used = bool(
            obligation_entities
            and isinstance(obligation_entities, dict)
            and obligation_entities.get("obligations")
        )
        if obligation_entities_used:
            contract_data["programme_compliance_model"] = None
            contract_data["required_activities"] = []

        # Mandatory-obligation existence assertion (contract completeness; does not decide acceptability).
        if obligation_entities_used:
            obligations_list = (contract_data.get("obligation_entities") or {}).get("obligations") or []
            mandatory_names = {
                (o.get("canonical_name") or o.get("original_contract_text") or "").strip().lower()
                for o in obligations_list
                if o.get("mandatory_for_acceptance")
            }
            if "temporary works" not in mandatory_names:
                raise RuntimeError(
                    "FATAL: Mandatory obligation 'Temporary Works' is missing from obligation_entities. "
                    "This indicates a contract analysis / obligation construction failure."
                )

        # Extract data once
        contract_summary = self._extract_contract_clauses(contract_data)
        programme_summary = self._extract_programme_data(p6_data)
        
        # Perform alignment (pass programme_summary to avoid re-extraction)
        nec_alignment = self._perform_nec_alignment_with_summary(
            contract_data, p6_data, programme_summary
        )
        
        # Assess risks (pass summaries to avoid re-extraction)
        risks = self._assess_risks_with_summaries(
            contract_data, p6_data, programme_summary, nec_alignment
        )
        
        # Generate detailed NEC alignment for all clauses
        nec_alignment_detailed = self._generate_nec_alignment_detailed(
            contract_summary, programme_summary, nec_alignment
        )
        
        # Calculate programme KPIs
        programme_kpis = self._calculate_programme_kpis(programme_summary, p6_data)
        
        # Generate structured recommendations
        recommendations = self._generate_recommendations(risks, nec_alignment, programme_summary)
        
        validation_output = {
            "contract_summary": contract_summary,
            "programme_summary": programme_summary,
            "nec_alignment": nec_alignment,
            "nec_alignment_detailed": nec_alignment_detailed,
            "programme_kpis": programme_kpis,
            "risks": risks,
            "risk_summary": risks,  # Alias for backward compatibility
            "recommendations": recommendations,
            "validation_summary": {},
            "metadata": {}
        }
        
        # Calculate validation summary
        validation_output["validation_summary"] = self._calculate_validation_summary(
            validation_output
        )

        scope_cov = (validation_output.get("nec_alignment") or {}).get("scope_coverage") or {}
        obligation_entities_used = isinstance(scope_cov, dict) and scope_cov.get("obligation_entities_used")

        # Tripwire after summary: required_activities and PCM must not be used in obligation mode.
        if obligation_entities_used and contract_data.get("required_activities"):
            raise RuntimeError("ILLEGAL: required_activities used in obligation mode")
        if obligation_entities_used and (validation_output.get("nec_alignment") or {}).get("programme_compliance_model"):
            raise RuntimeError("ILLEGAL: PCM used in obligation mode")

        vs = validation_output.get("validation_summary") or {}
        obligations_report = scope_cov.get("obligations_report") or []

        # FINAL INVARIANT: If any mandatory obligation has aligned == False, the system must NEVER return pass or "Acceptable at this stage". Tripwire only when summary contradicts (says acceptable but we have unaligned mandatory).
        if obligation_entities_used:
            failing = [
                o.get("id") for o in obligations_report
                if o.get("mandatory_for_acceptance") and not o.get("aligned")
            ]
            acceptable_status = vs.get("acceptability_status") == "ACCEPTABLE"
            overall_pass = vs.get("overall_status") == "pass"
            if failing and (acceptable_status or overall_pass):
                raise RuntimeError(
                    "FATAL: Programme marked acceptable with unaligned mandatory obligations: {}".format(failing)
                )
            covered_later = [
                o.get("id") for o in obligations_report
                if o.get("mandatory_for_acceptance") and (o.get("explicit_assumption") or "").strip().lower() == "covered_by_later_submission"
            ]
            if covered_later and (acceptable_status or overall_pass):
                raise RuntimeError(
                    "FATAL: Programme marked acceptable while mandatory obligation(s) have only 'covered_by_later_submission' (advisory only; must not justify acceptance): {}".format(covered_later)
                )

        return validation_output
    
    def _is_new_contract_format(self, contract_data: Dict[str, Any]) -> bool:
        """True if contract JSON is from analyze_contract (project/contract_dates/programme_compliance_model)."""
        return (
            "programme_compliance_model" in contract_data
            or ("contract_dates" in contract_data and "extracted_clauses" not in contract_data)
        )

    def _extract_contract_clauses(self, contract_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract all NEC clauses and meaningful fields from contract JSON (legacy or new format)."""
        extracted_clauses = contract_data.get("extracted_clauses", {})
        contract_dates = contract_data.get("contract_dates", {})
        payment_terms = contract_data.get("payment_terms", {})
        programme_requirements = contract_data.get("programme_requirements", {})
        programme_requirements_detailed = contract_data.get("programme_requirements_detailed", {})
        delay_damages = contract_data.get("delay_damages", "")
        weather_data = contract_data.get("weather_data", {})
        defects = contract_data.get("defects", {})
        pcm = contract_data.get("programme_compliance_model", {})

        # New format: top-level contract_dates, programme_requirements_detailed, etc.
        if self._is_new_contract_format(contract_data):
            pr = programme_requirements_detailed or programme_requirements or {}
            contract_summary = {
                "starting_date": {
                    "value": contract_dates.get("starting_date", ""),
                    "status": "present" if contract_dates.get("starting_date") else "missing"
                },
                "completion_date": {
                    "value": contract_dates.get("completion_date", ""),
                    "status": "present" if contract_dates.get("completion_date") else "missing"
                },
                "retention_percentage": {
                    "value": payment_terms.get("retention_percentage", "") if isinstance(payment_terms, dict) else "",
                    "status": "present" if (isinstance(payment_terms, dict) and payment_terms.get("retention_percentage")) else "missing"
                },
                "submit_first_programme_within": {
                    "value": pr.get("submit_first_programme_within", ""),
                    "status": "present" if pr.get("submit_first_programme_within") else "missing"
                },
                "revised_programme_interval": {
                    "value": pr.get("revised_programme_interval", ""),
                    "status": "present" if pr.get("revised_programme_interval") else "missing"
                },
                "delay_damages": {
                    "value": delay_damages or "",
                    "status": "present" if delay_damages else "missing"
                },
                "weather_data": {
                    "recording_location": weather_data.get("recording_location", "") if isinstance(weather_data, dict) else "",
                    "measurement_data": weather_data.get("measurement_data", "") if isinstance(weather_data, dict) else "",
                    "historical_records_source": weather_data.get("historical_records_source", "") if isinstance(weather_data, dict) else "",
                    "status": "present" if (isinstance(weather_data, dict) and weather_data.get("recording_location")) else "missing"
                },
                "clauses": {},
                "programme_compliance_model": pcm,
                "scope_items": contract_data.get("scope_items", []),
                "constraints": contract_data.get("constraints", []),
                "milestones": contract_data.get("milestones", []),
                "defects": defects,
            }
            return contract_summary

        # Legacy format: extracted_clauses
        contract_summary = {
            "starting_date": {
                "value": contract_dates.get("starting_date", "") or extracted_clauses.get("3.1", {}).get("value", ""),
                "status": "present" if (contract_dates.get("starting_date") or extracted_clauses.get("3.1", {}).get("value")) else "missing"
            },
            "completion_date": {
                "value": contract_dates.get("completion_date", "") or extracted_clauses.get("3.3", {}).get("value", ""),
                "status": "present" if (contract_dates.get("completion_date") or extracted_clauses.get("3.3", {}).get("value")) else "missing"
            },
            "retention_percentage": {
                "value": payment_terms.get("retention_percentage", "") or extracted_clauses.get("5.5", {}).get("value", ""),
                "status": "present" if (payment_terms.get("retention_percentage") or extracted_clauses.get("5.5", {}).get("value")) else "missing"
            },
            "submit_first_programme_within": {
                "value": programme_requirements.get("submit_first_programme_within", "") or extracted_clauses.get("3.5", {}).get("value", ""),
                "status": "present" if (programme_requirements.get("submit_first_programme_within") or extracted_clauses.get("3.5", {}).get("value")) else "missing"
            },
            "revised_programme_interval": {
                "value": programme_requirements.get("revised_programme_interval", "") or extracted_clauses.get("3.6", {}).get("value", ""),
                "status": "present" if (programme_requirements.get("revised_programme_interval") or extracted_clauses.get("3.6", {}).get("value")) else "missing"
            },
            "delay_damages": {
                "value": delay_damages if delay_damages else (extracted_clauses.get("3.7", {}).get("value", "")),
                "status": "present" if (delay_damages or extracted_clauses.get("3.7", {}).get("value")) else "missing"
            },
            "weather_data": {
                "recording_location": weather_data.get("recording_location", "") or extracted_clauses.get("6.1", {}).get("value", ""),
                "measurement_data": weather_data.get("measurement_data", "") or extracted_clauses.get("6.2", {}).get("value", ""),
                "historical_records_source": weather_data.get("historical_records_source", "") or extracted_clauses.get("6.3", {}).get("value", ""),
                "status": "present" if (weather_data.get("recording_location") or extracted_clauses.get("6.1", {}).get("value")) else "missing"
            },
            "clauses": {}
        }
        clause_keys = [
            "3.1", "3.2", "3.3", "3.5", "3.6", "3.7",
            "4.1", "4.2", "4.3", "5.2", "5.3", "5.5", "5.6", "6.1", "6.2", "6.3",
        ]
        for key in clause_keys:
            clause = extracted_clauses.get(key, {})
            contract_summary["clauses"][key] = {
                "title": clause.get("title", ""),
                "value": clause.get("value", ""),
                "status": clause.get("status", "missing")
            }
        return contract_summary
    
    def _extract_programme_data(self, p6_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract comprehensive programme data from XER."""
        activities = p6_data.get("activities", [])
        calendars = p6_data.get("calendars", [])
        logic = p6_data.get("logic", [])
        constraints = p6_data.get("constraints", [])
        metadata = p6_data.get("metadata", {})
        wbs_list = p6_data.get("wbs", []) or []

        # Build wbs_id -> full path (e.g. "Project / Phase 1 / Temporary Works")
        wbs_id_to_path: Dict[str, str] = {}
        wbs_by_id = {(n.get("wbs_id") or "").strip(): n for n in wbs_list if (n.get("wbs_id") or "").strip()}
        def path_for(wbs_id: str) -> str:
            if not wbs_id or wbs_id in wbs_id_to_path:
                return wbs_id_to_path.get(wbs_id, "")
            node = wbs_by_id.get(wbs_id)
            if not node:
                return ""
            name = (node.get("wbs_name") or node.get("name") or "").strip()
            parent_id = (node.get("parent_wbs_id") or "").strip()
            if not parent_id:
                wbs_id_to_path[wbs_id] = name
                return name
            parent_path = path_for(parent_id)
            out = f"{parent_path} / {name}" if parent_path else name
            wbs_id_to_path[wbs_id] = out
            return out
        for n in wbs_list:
            wid = (n.get("wbs_id") or "").strip()
            if wid:
                path_for(wid)

        # Extract activity details (include wbs_path for obligation rules e.g. Temporary Works)
        activity_details = []
        for act in activities:
            wbs_id = (act.get("wbs_id") or act.get("proj_node_id") or "").strip()
            wbs_path = wbs_id_to_path.get(wbs_id, "") if wbs_id else ""
            activity_details.append({
                "id": act.get("task_id") or act.get("id", ""),
                "name": act.get("task_name") or act.get("name", ""),
                "start": act.get("start_date") or act.get("start", ""),
                "finish": act.get("finish_date") or act.get("finish", ""),
                "calendar": act.get("calendar_id") or act.get("calendar", ""),
                "float": float(act.get("total_float", 0) or 0),
                "critical": act.get("critical_flag", False) or (float(act.get("total_float", 0) or 0) <= 0),
                "wbs_path": wbs_path,
            })
        
        # Extract data date
        data_date = metadata.get("data_date", "")
        
        # Programme start/finish: prefer start and finish milestones (earliest start, latest finish), else min/max activity dates
        start_milestone_dates = []
        finish_milestone_dates = []
        for act in activities:
            name = (act.get("task_name") or act.get("name") or "").lower()
            task_type = (act.get("task_type") or "").strip()
            start = act.get("start_date") or act.get("start", "")
            finish = act.get("finish_date") or act.get("finish", "")
            if not start and not finish:
                continue
            # Start milestone: TT_Mile or name like "start milestone" (exclude "finish" so we don't pick Finish Milestone)
            if (task_type == "TT_Mile" or ("start" in name and "milestone" in name)) and "finish" not in name:
                d = start or finish
                if d:
                    start_milestone_dates.append(d)
            # Finish/Completion milestone: TT_FinMile or name "completion" or "finish milestone" (project end, not gate key)
            if task_type == "TT_FinMile" or name == "completion" or (name == "finish milestone"):
                d = finish or start
                if d:
                    finish_milestone_dates.append(d)
            elif "completion" in name and task_type != "TT_Mile":
                d = finish or start
                if d:
                    finish_milestone_dates.append(d)
        earliest_start = None
        latest_finish = None
        for act in activity_details:
            start = act.get("start")
            finish = act.get("finish")
            if start and (not earliest_start or start < earliest_start):
                earliest_start = start
            if finish and (not latest_finish or finish > latest_finish):
                latest_finish = finish
        programme_start_date = min(start_milestone_dates) if start_milestone_dates else earliest_start
        programme_finish_date = max(finish_milestone_dates) if finish_milestone_dates else latest_finish
        
        # Find critical path activities
        critical_path = [a for a in activity_details if a["critical"]]
        
        # Find out-of-sequence activities
        out_of_sequence = []
        for act in activities:
            if act.get("actual_start") and act.get("start_date"):
                if act.get("actual_start") < act.get("start_date"):
                    out_of_sequence.append({
                        "id": act.get("task_id") or act.get("id", ""),
                        "name": act.get("task_name") or act.get("name", ""),
                        "issue": "Actual start before planned start"
                    })
        
        # Find dangling logic
        activity_ids = {a.get("task_id") or a.get("id", "") for a in activities}
        dangling_logic = []
        for rel in logic:
            pred_id = rel.get("pred_task_id") or rel.get("predecessor_id", "")
            succ_id = rel.get("succ_task_id") or rel.get("successor_id", "")
            if pred_id and pred_id not in activity_ids:
                dangling_logic.append({"type": "predecessor", "id": pred_id})
            if succ_id and succ_id not in activity_ids:
                dangling_logic.append({"type": "successor", "id": succ_id})
        
        # Calculate total float distribution
        float_values = [a["float"] for a in activity_details]
        float_distribution = {
            "negative": len([f for f in float_values if f < 0]),
            "zero": len([f for f in float_values if f == 0]),
            "low_positive": len([f for f in float_values if 0 < f <= 7]),
            "medium_positive": len([f for f in float_values if 7 < f <= 30]),
            "high_positive": len([f for f in float_values if f > 30])
        }
        
        # Find negative float list
        negative_float_list = [
            {"id": a["id"], "name": a["name"], "float": a["float"]}
            for a in activity_details if a["float"] < 0
        ]
        
        # Find key milestones (TT_Mile, TT_FinMile, or zero duration)
        key_milestones = []
        for act in activities:
            task_type = (act.get("task_type") or "").strip()
            is_milestone = (
                act.get("milestone_flag")
                or (act.get("duration", 0) == 0 and act.get("remain_drtn_hr_cnt", 0) == 0)
                or task_type in ("TT_Mile", "TT_FinMile")
            )
            if is_milestone:
                key_milestones.append({
                    "id": act.get("task_id") or act.get("id", ""),
                    "name": act.get("task_name") or act.get("name", ""),
                    "date": act.get("finish_date") or act.get("finish", "") or act.get("early_end_date", "") or act.get("act_end_date", "")
                })
        
        # Get circular dependencies (will be populated by logic_checks)
        circular_dependencies = []  # Will be filled from logic_checks
        
        # Get logic errors (broken logic)
        logic_errors = []
        for rel in logic:
            pred_id = rel.get("pred_task_id") or rel.get("predecessor_id", "")
            succ_id = rel.get("succ_task_id") or rel.get("successor_id", "")
            if (pred_id and pred_id not in activity_ids) or (succ_id and succ_id not in activity_ids):
                logic_errors.append({
                    "type": "broken_relationship",
                    "predecessor": pred_id,
                    "successor": succ_id
                })
        
        return {
            "data_date": data_date,
            "programme_start_date": programme_start_date,
            "programme_finish_date": programme_finish_date,
            "earliest_activity_start": earliest_start,
            "latest_activity_finish": latest_finish,
            "list_of_milestones": key_milestones,
            "list_of_calendars": calendars,
            "critical_path": critical_path,
            "total_float_distribution": float_distribution,
            "negative_float_list": negative_float_list,
            "out_of_sequence_activities": out_of_sequence,
            "circular_dependencies": circular_dependencies,  # Will be populated from logic_checks
            "logic_errors": logic_errors,
            "constraints": constraints,
            "activities": activity_details,  # Keep for backward compatibility
            "total_activities": len(activity_details),
            "total_calendars": len(calendars),
            "total_logic_relationships": len(logic),
            "metadata": metadata,
        }
    
    def _perform_nec_alignment(
        self,
        contract_data: Dict[str, Any],
        p6_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform comprehensive NEC alignment checks."""
        programme_summary = self._extract_programme_data(p6_data)
        return self._perform_nec_alignment_with_summary(contract_data, p6_data, programme_summary)
    
    def _perform_nec_alignment_with_summary(
        self,
        contract_data: Dict[str, Any],
        p6_data: Dict[str, Any],
        programme_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform comprehensive NEC alignment checks with pre-extracted programme summary."""
        # HARD DISABLE legacy PCM / required_activities when obligation alignment is active.
        obligation_entities = contract_data.get("obligation_entities") or {}
        obligation_entities_used = bool(
            obligation_entities
            and isinstance(obligation_entities, dict)
            and obligation_entities.get("obligations")
        )
        if obligation_entities_used:
            contract_data["programme_compliance_model"] = None
            contract_data["required_activities"] = []

        activities = programme_summary.get("activities", [])
        activity_names_lower = [(a.get("name") or "").lower() for a in activities]

        # Source contract values from new format or legacy extracted_clauses
        if self._is_new_contract_format(contract_data):
            contract_dates = contract_data.get("contract_dates", {})
            pr_detailed = contract_data.get("programme_requirements_detailed", {}) or contract_data.get("programme_requirements", {})
            contract_start = contract_dates.get("starting_date", "")
            contract_completion = contract_dates.get("completion_date", "")
            access_dates = contract_dates.get("access_dates", [])
            possession_dates = ", ".join(str(d) for d in access_dates) if isinstance(access_dates, list) else (access_dates or "")
            first_submission = pr_detailed.get("submit_first_programme_within", "")
            revision_interval = pr_detailed.get("revised_programme_interval", "")
            delay_damages = contract_data.get("delay_damages", "") or ""
            weather_data = contract_data.get("weather_data", {}) or {}
            weather_location = weather_data.get("recording_location", "") if isinstance(weather_data, dict) else ""
        else:
            contract_clauses = contract_data.get("extracted_clauses", {})
            contract_start = contract_clauses.get("3.1", {}).get("value", "")
            contract_completion = contract_clauses.get("3.3", {}).get("value", "")
            possession_dates = contract_clauses.get("3.2", {}).get("value", "")
            first_submission = contract_clauses.get("3.5", {}).get("value", "")
            revision_interval = contract_clauses.get("3.6", {}).get("value", "")
            delay_damages = contract_clauses.get("3.7", {}).get("value", "") or contract_data.get("delay_damages", "")
            weather_location = contract_clauses.get("6.1", {}).get("value", "")

        alignment = {}
        # Programme dates: prefer start/finish milestones, else earliest/latest activity dates
        programme_start = programme_summary.get("programme_start_date") or programme_summary.get("earliest_activity_start")
        programme_finish = programme_summary.get("programme_finish_date") or programme_summary.get("latest_activity_finish")
        if not programme_finish:
            for act in activities:
                finish = act.get("finish")
                if finish and (not programme_finish or finish > programme_finish):
                    programme_finish = finish

        # A. Start Date Alignment (contract start vs programme start from TASK table / milestones)
        alignment["starting_date"] = self._create_alignment_entry(
            contract_start, programme_start or programme_summary.get("data_date", ""), "Starting Date"
        )

        # B. Completion Date (contract vs programme; if programme uses standard 5-day workweek/worksheet schedule,
        # contract completion on a weekend (Sat/Sun) does not count—programme completing next working day is aligned)
        calendars = programme_summary.get("list_of_calendars", programme_summary.get("calendars", [])) or []
        calendar_names = " ".join(
            (c.get("clndr_name", "") if isinstance(c, dict) else str(c)) for c in calendars
        ).lower()
        programme_5day = (
            "5" in calendar_names
            and (
                "day" in calendar_names
                or "workweek" in calendar_names
                or "work week" in calendar_names
                or "worksheet" in calendar_names
                or "schedule" in calendar_names
            )
        )
        alignment["completion_date"] = self._create_completion_alignment_entry(
            contract_completion, programme_finish, "Completion Date", programme_uses_5day_workweek=programme_5day
        )

        # C. Possession / Access (SEMANTIC: compliant if programme start >= contractual access date; HARD_BREACH if programme start < access)
        earliest_start = None
        for act in activities:
            start = act.get("start")
            if start and (not earliest_start or start < earliest_start):
                earliest_start = start
        alignment["possession_dates"] = self._create_possession_alignment_entry(
            possession_dates, earliest_start, "Possession / Access"
        )
        
        # D. Key Dates
        alignment["key_dates"] = self._check_key_dates(contract_data, programme_summary)

        # E. Programme Submission Rules
        alignment["programme_submission"] = {
            "first_submission": {
                "contract": first_submission,
                "programme": "N/A",  # Programme doesn't have this directly
                "variance_days": None,
                "status": "present" if first_submission else "contract_missing",
                "reason": "First programme submission requirement" if first_submission else "Contract clause 3.5 missing"
            },
            "revision_interval": {
                "contract": revision_interval,
                "programme": "N/A",
                "variance_days": None,
                "status": "present" if revision_interval else "contract_missing",
                "reason": "Revised programme interval requirement" if revision_interval else "Contract clause 3.6 missing"
            }
        }
        
        # F. Delay Damages
        completion_activities = [
            a for a in activities
            if "completion" in a.get("name", "").lower() or "finish" in a.get("name", "").lower()
        ]
        alignment["delay_damages_alignment"] = {
            "contract": delay_damages if delay_damages else "Not specified",
            "programme": f"{len(completion_activities)} completion activities" if completion_activities else "No completion activities",
            "variance_days": None,
            "status": "aligned" if (delay_damages and completion_activities) else ("contract_missing" if not delay_damages else "programme_missing"),
            "reason": "Delay damages specified and completion activities present" if (delay_damages and completion_activities) else ("Contract delay damages clause missing" if not delay_damages else "Programme missing completion activities")
        }
        
        # G. Weather (informational only: contract weather location is for compensation-event data, not a programme requirement to have a weather calendar)
        calendars = programme_summary.get("list_of_calendars", programme_summary.get("calendars", [])) or []
        weather_calendars = [
            c for c in calendars
            if "weather" in str(c).lower() or "rain" in str(c).lower()
        ]
        alignment["weather_alignment"] = {
            "contract": weather_location if weather_location else "Not specified",
            "programme": f"{len(weather_calendars)} weather calendars" if weather_calendars else "No weather calendars",
            "variance_days": None,
            "status": "aligned" if (weather_location and weather_calendars) else ("info" if weather_location else "contract_missing"),
            "reason": "Weather location specified and weather calendars present" if (weather_location and weather_calendars) else ("Contract weather is for compensation-event data; programme calendar not required for alignment" if weather_location else "Contract weather clause missing")
        }

        # H. Programme compliance model — MUST NOT be generated when obligation alignment is active.
        # When obligation_entities_used: do not generate PCM; required_activities must be empty; no scoring/PCM may influence acceptability.
        frozen_list = contract_data.get("frozen_requirements") or []
        frozen_primary_used = isinstance(frozen_list, list) and len(frozen_list) > 0
        if obligation_entities_used:
            alignment["programme_compliance_model"] = None
        else:
            pcm = contract_data.get("programme_compliance_model", {})
            if pcm:
                alignment["programme_compliance_model"] = self._validate_programme_compliance_model(
                    contract_data,
                    pcm,
                    programme_summary,
                    activity_names_lower,
                    activities
                )
                if frozen_primary_used and isinstance(alignment.get("programme_compliance_model"), dict):
                    alignment["programme_compliance_model"]["required_activities_diagnostic_only"] = True
                    alignment["programme_compliance_model"]["required_activities_note"] = (
                        "Acceptability is determined only by obligation evidence. "
                        "Other programme expectations are for explanation only."
                    )

        # Execution-order guards: when obligation_entities_used, PCM must not run and required_activities must not be used.
        if obligation_entities_used:
            if alignment.get("programme_compliance_model") is not None:
                raise RuntimeError(
                    "CONTRADICTION: obligation_entities_used but PCM was set. PCM must not run when obligation alignment is active."
                )
            if contract_data.get("required_activities"):
                raise RuntimeError(
                    "CONTRADICTION: obligation_entities_used but required_activities is non-empty. required_activities must be ignored when obligation alignment is active."
                )

        # I. Scope coverage: obligation entities (single deduplicated list) or frozen list or legacy
        obligation_entities = contract_data.get("obligation_entities") or {}
        obligations_list = obligation_entities.get("obligations") if isinstance(obligation_entities, dict) else None
        has_obligation_entities = isinstance(obligations_list, list) and len(obligations_list) > 0
        if has_obligation_entities:
            alignment["scope_coverage"] = self._validate_obligation_entities(
                contract_data,
                programme_summary,
                activities,
            )
        elif frozen_primary_used:
            alignment["scope_coverage"] = self._validate_against_frozen_requirements(
                contract_data,
                programme_summary,
                activities,
            )
            expected_reps = contract_data.get("expected_programme_representations") or []
            if expected_reps:
                alignment["scope_coverage"]["expected_programme_representations"] = expected_reps
                alignment["scope_coverage"]["expected_programme_representations_note"] = (
                    "Expected programme representations (derived from primary obligations; "
                    "for explanation only; do not drive acceptability). Each item references parent_obligation_id."
                )
        else:
            alignment["scope_coverage"] = self._validate_scope_coverage(
                contract_data,
                programme_summary,
                activity_names_lower,
                activities,
            )

        # Attach traceability and outcome to every alignment entry (source_clause, source_type, validation_basis, importance_tier, outcome)
        for key in list(alignment.keys()):
            entry = alignment[key]
            if isinstance(entry, dict) and "status" in entry and "outcome" not in entry:
                attach_traceability(entry, key)
            elif isinstance(entry, dict) and "first_submission" in entry:
                for subkey, sub in (("first_submission", entry.get("first_submission")), ("revision_interval", entry.get("revision_interval"))):
                    if isinstance(sub, dict) and "outcome" not in sub:
                        sub["importance_tier"] = TIER_3_INFORMATIONAL
                        sub["source_clause"] = "Clause 32 / 3.5" if subkey == "first_submission" else "Clause 32 / 3.6"
                        sub["source_type"] = "explicit"
                        sub["validation_basis"] = "existence"
                        sub["outcome"] = COMPLIANT  # TIER_3 never breach

        return alignment

    def _validate_programme_compliance_model(
        self,
        contract_data: Dict[str, Any],
        pcm: Dict[str, Any],
        programme_summary: Dict[str, Any],
        activity_names_lower: List[str],
        activities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Validate programme against programme_compliance_model (required_activities, completion_gates, etc.)."""
        contract_context = _determine_contract_context(contract_data, programme_summary)
        stage_info = _determine_programme_stage(contract_data, programme_summary, activities)
        stage = stage_info["stage"]

        contract_required_activities = _deduplicate_required_activities(pcm.get("required_activities", []) or [])
        expectation_entries = _assign_expectation_flags(contract_required_activities, stage)
        expectation_policy = _expectation_policy_for_stage(stage)

        result = {
            "programme_stage": stage,
            "programme_stage_label": stage_info.get("stage_label", _STAGE_TITLES.get(stage, stage)),
            "programme_stage_reasoning": stage_info.get("reasoning", ""),
            "programme_stage_signals": stage_info.get("signals", {}),
            "programme_stage_signals_used": stage_info.get("signals_used", []),
            "programme_stage_signals_ignored": stage_info.get("signals_ignored", []),
            "programme_stage_exclusions": stage_info.get("excluded", {}),
            "contract_type": contract_context.get("contract_type", "UNKNOWN"),
            "programme_intent": contract_context.get("programme_intent", "mixed"),
            "required_activity_expectation_policy": expectation_policy,
            "contract_required_activities": contract_required_activities,
            "required_activities": {
                "entries": [],
                "matched": [],
                "missing": [],
                "status": "unknown",
                "summary": "",
                "total_contract_required_activities": len(contract_required_activities),
                "expected_now_total": 0,
                "expected_now_found": 0,
                "expected_now_missing": 0,
                "expected_later_total": 0,
                "expected_later_found": 0,
                "expected_later_missing": 0,
                "total_required_activities": len(contract_required_activities),
                "matched_required_activities": 0,
                "missing_required_activities": 0,
                "acceptability_basis": EXPECTED_NOW,
            },
            "completion_and_takeover_gates": {"matched": [], "missing": [], "status": "unknown", "summary": ""},
            "sequencing_and_timing_constraints": {"notes": [], "status": "unknown"},
            "overall_status": "unknown",
        }
        all_activity_text = " ".join(activity_names_lower)
        programme_activity_details: List[Dict[str, Any]] = []
        for activity in activities:
            name = (activity.get("name") or "").strip()
            lower = name.lower()
            programme_activity_details.append({
                "name": name,
                "name_lower": lower,
                "intent": _extract_semantic_intent(name),
            })

        entries = result["required_activities"]["entries"]
        matched_requirements = result["required_activities"]["matched"]
        missing_requirements = result["required_activities"]["missing"]
        expected_now_total = expected_now_found = expected_now_missing = 0
        expected_later_total = expected_later_found = expected_later_missing = 0

        # Match against the fixed contract list; expectation flags never change or remove items
        for expectation_entry in expectation_entries:
            requirement_text = expectation_entry["requirement"]
            expectation = expectation_entry["expectation"]
            expectation_reason = expectation_entry["expectation_reason"]

            req_lower = requirement_text.lower()
            req_intent = _extract_semantic_intent(requirement_text)

            matched_entry: Optional[Dict[str, Any]] = None
            match_basis = "semantic intent"
            match_explanation = ""

            for detail in programme_activity_details:
                name_lower = detail["name_lower"]
                if not name_lower:
                    continue
                if req_lower in name_lower or name_lower in req_lower:
                    matched_entry = detail
                    match_basis = "exact"
                    match_explanation = f'Exact text match: requirement phrase appears within programme activity "{detail["name"]}".'
                    break

            if not matched_entry:
                for detail in programme_activity_details:
                    if _semantic_intent_match(req_intent, detail["intent"]):
                        matched_entry = detail
                        match_basis = "semantic intent"
                        shared_actions = sorted(req_intent["actions"] & detail["intent"]["actions"])
                        shared_nouns = sorted(req_intent["nouns"] & detail["intent"]["nouns"])
                        explanation_bits: List[str] = []
                        if shared_actions:
                            explanation_bits.append(f"shared action(s) {', '.join(shared_actions)}")
                        if shared_nouns:
                            explanation_bits.append(f"shared noun(s) {', '.join(shared_nouns)}")
                        match_explanation = (
                            "Semantic intent match based on "
                            + (" and ".join(explanation_bits) if explanation_bits else "overlapping programme keywords.")
                        )
                        break

            matched_programme_activities = [matched_entry["name"]] if matched_entry else []
            status = "FOUND" if matched_entry else "NOT_FOUND"

            entries.append({
                "requirement": requirement_text,
                "expectation": expectation,
                "expectation_reason": expectation_reason,
                "status": status,
                "matched_programme_activities": matched_programme_activities,
                "matching_basis": match_basis,
                "matching_explanation": match_explanation or ("Not matched." if not matched_entry else ""),
            })

            if status == "FOUND":
                matched_requirements.append(requirement_text)
            else:
                missing_requirements.append(requirement_text)

            if expectation == EXPECTED_NOW:
                expected_now_total += 1
                if status == "FOUND":
                    expected_now_found += 1
                else:
                    expected_now_missing += 1
            else:
                expected_later_total += 1
                if status == "FOUND":
                    expected_later_found += 1
                else:
                    expected_later_missing += 1

        total_contract = len(entries)
        assert expected_now_total + expected_later_total == total_contract, "Expectation subsets must cover all contract-required activities"

        result["required_activities"]["total_contract_required_activities"] = total_contract
        result["required_activities"]["total_required_activities"] = total_contract  # Backward compatibility
        result["required_activities"]["expected_now_total"] = expected_now_total
        result["required_activities"]["expected_now_found"] = expected_now_found
        result["required_activities"]["expected_now_missing"] = expected_now_missing
        result["required_activities"]["expected_later_total"] = expected_later_total
        result["required_activities"]["expected_later_found"] = expected_later_found
        result["required_activities"]["expected_later_missing"] = expected_later_missing
        result["required_activities"]["matched_required_activities"] = expected_now_found
        result["required_activities"]["missing_required_activities"] = expected_now_missing

        if total_contract == 0:
            req_status = "pass"
            result["required_activities"]["summary"] = (
                "No contract required activities were identified; none are expected at this stage."
            )
        else:
            req_status = "pass" if expected_now_missing == 0 else "fail"
            summary_parts = [
                f"Contract obligations: {total_contract} activities (expected now: {expected_now_total}, expected later: {expected_later_total}).",
                f"Expected-now found: {expected_now_found}/{expected_now_total}; missing: {expected_now_missing}.",
                "Expected-later activities remain informational and are shown below."
            ]
            result["required_activities"]["summary"] = " ".join(summary_parts)

        result["required_activities"]["status"] = req_status
        result["required_activities"]["stage"] = stage
        result["required_activities"]["importance_tier"] = TIER_1_CRITICAL
        result["required_activities"]["source_clause"] = "Programme Compliance Model"
        result["required_activities"]["source_type"] = "explicit"
        result["required_activities"]["validation_basis"] = "semantic_intent"
        if req_status == "pass":
            result["required_activities"]["outcome"] = COMPLIANT
        else:
            result["required_activities"]["outcome"] = HARD_BREACH
            result["required_activities"]["failure_reason"] = "Programme representation expectations not met (diagnostic only; acceptability is obligation-based)."

        # Completion and takeover gates: same fuzzy match
        gates = pcm.get("completion_and_takeover_gates", [])
        for gate in gates:
            gate_lower = (gate if isinstance(gate, str) else str(gate)).lower()
            tokens = [t for t in gate_lower.replace(",", " ").split() if len(t) > 3]
            if not tokens:
                tokens = [gate_lower[:20]] if len(gate_lower) >= 10 else []
            found = any(
                all(tok in name for tok in tokens) or (tokens and tokens[0] in name)
                for name in activity_names_lower
            ) or any(tok in all_activity_text for tok in tokens)
            if found:
                result["completion_and_takeover_gates"]["matched"].append(gate)
            else:
                result["completion_and_takeover_gates"]["missing"].append(gate)
        n_gates = len(gates)
        n_gmatched = len(result["completion_and_takeover_gates"]["matched"])
        result["completion_and_takeover_gates"]["status"] = "pass" if (n_gates == 0 or n_gmatched == n_gates) else ("partial" if n_gmatched > 0 else "fail")
        result["completion_and_takeover_gates"]["summary"] = f"{n_gmatched}/{n_gates} completion gates reflected in programme" if n_gates else "No completion gates specified"
        result["completion_and_takeover_gates"]["importance_tier"] = TIER_1_CRITICAL
        result["completion_and_takeover_gates"]["source_clause"] = "Programme Compliance Model"
        result["completion_and_takeover_gates"]["source_type"] = "explicit"
        result["completion_and_takeover_gates"]["validation_basis"] = "logic"
        st_gates = result["completion_and_takeover_gates"]["status"]
        result["completion_and_takeover_gates"]["outcome"] = COMPLIANT if st_gates == "pass" else (SOFT_BREACH if st_gates == "partial" else HARD_BREACH)

        # Sequencing/timing: informational (we don't parse "must not obstruct" from programme)
        seq = pcm.get("sequencing_and_timing_constraints", [])
        result["sequencing_and_timing_constraints"]["notes"] = seq
        result["sequencing_and_timing_constraints"]["status"] = "info" if seq else "n/a"

        # Overall: fail only on completion/takeover gates. Required activities = same concept as scope items;
        # scope_coverage check is the single gate for activity/scope/constraint missing.
        if result["completion_and_takeover_gates"]["status"] == "fail":
            result["overall_status"] = "fail"
        elif result["completion_and_takeover_gates"]["status"] == "partial":
            result["overall_status"] = "partial"
        else:
            result["overall_status"] = "pass"
        return result

    # Trailing qualifiers that describe how/when (no separate programme activity required)
    _COMPONENT_QUALIFIER_STARTS = ("including when", "when instructed", "as directed", "if instructed", "unless instructed", "as required", "where applicable")

    # Minimum length for a phrase to match an activity (avoids "in", "to", "by" etc.)
    _EVIDENCE_PHRASE_MIN_LEN = 3
    # Require at least this many phrases to match in an activity name so that single-word matches
    # (e.g. "materials" in an unrelated activity) do not falsely evidence a scope item.
    _MIN_PHRASES_TO_EVIDENCE = 2

    def _extract_evidence_phrases(self, text: str) -> List[str]:
        """
        Extract phrases from obligation text for phrase-based evidence matching.
        An activity evidences the obligation only if it contains enough matching phrases (see _phrase_evidences_obligation).
        """
        if not text or not text.strip():
            return []
        t = text.strip().lower()
        for sep in [" to ", " and ", ", "]:
            t = t.replace(sep, "|")
        parts = [p.strip() for p in t.split("|") if p.strip() and len(p.strip()) >= self._EVIDENCE_PHRASE_MIN_LEN]
        merged: List[str] = []
        for p in parts:
            if p == "in advance" and merged:
                merged[-1] = merged[-1] + " in advance"
            else:
                merged.append(p)
        filtered = [p for p in merged if not any(p.startswith(q) for q in self._COMPONENT_QUALIFIER_STARTS)]
        phrases: Set[str] = set()
        for p in filtered:
            phrases.add(p)
            for w in p.split():
                if len(w) >= self._EVIDENCE_PHRASE_MIN_LEN:
                    phrases.add(w)
        return sorted(phrases)

    def _phrase_evidences_obligation(self, activity_name_lower: str, phrases: List[str]) -> bool:
        """
        True if the activity name substantively evidences the obligation.
        Requires at least MIN_PHRASES_TO_EVIDENCE distinct phrases to match (or one multi-word phrase),
        so that a single word (e.g. 'materials') in an unrelated activity does not falsely evidence
        a scope item and cause a programme with missing scope to be accepted.
        """
        if not activity_name_lower or not phrases:
            return False
        matched: List[str] = []
        for p in phrases:
            if len(p) >= self._EVIDENCE_PHRASE_MIN_LEN and p in activity_name_lower:
                matched.append(p)
        if not matched:
            return False
        # One multi-word phrase is enough (e.g. "store materials" in "Store materials on site")
        if any(" " in m for m in matched):
            return True
        # Single-phrase obligation: one match is enough
        if len(phrases) <= 1:
            return True
        # Multiple phrases: require at least MIN_PHRASES_TO_EVIDENCE so one word doesn't falsely evidence scope
        return len(matched) >= self._MIN_PHRASES_TO_EVIDENCE

    def _extract_obligation_action_components(self, text: str) -> List[str]:
        """Decompose obligation text into action components (verb phrases) for compound evidence.
        E.g. 'Select, procure in advance, and store materials' -> ['select', 'procure in advance', 'store materials'].
        If commas split out 'in advance' (e.g. 'Select, procure, in advance, and store materials'), merge it with the previous component.
        Trailing qualifiers (e.g. 'including when instructed by the Project Manager') are dropped so they do not require evidence.
        """
        if not text or not text.strip():
            return []
        t = text.strip().lower()
        for sep in [" to ", " and ", ", "]:
            t = t.replace(sep, "|")
        parts = [p.strip() for p in t.split("|") if p.strip() and len(p.strip()) >= 2]
        # Merge standalone "in advance" with previous component so "procure" + "in advance" -> "procure in advance"
        merged: List[str] = []
        for p in parts:
            if p == "in advance" and merged:
                merged[-1] = merged[-1] + " in advance"
            else:
                merged.append(p)
        # Drop trailing qualifier phrases (no programme activity required for "including when instructed...", etc.)
        filtered = [p for p in merged if not any(p.startswith(q) for q in self._COMPONENT_QUALIFIER_STARTS)]
        seen: Set[str] = set()
        out: List[str] = []
        for p in filtered:
            if p not in seen:
                seen.add(p)
                out.append(p)
        return out

    def _activity_covers_component(self, activity_name_lower: str, component: str) -> bool:
        """True if this activity evidences the given action component (substring or all significant words)."""
        if not activity_name_lower or not component:
            return False
        comp_stripped = component.strip()
        # Standalone timing qualifier "in advance" does not require an activity; satisfied by programme structure.
        if comp_stripped == "in advance":
            return True
        if component in activity_name_lower:
            return True
        # Procure/procurement equivalence (e.g. "Materials procurement" evidences "procure in advance").
        if comp_stripped == "procure" and "procurement" in activity_name_lower:
            return True
        if comp_stripped == "procurement" and "procure" in activity_name_lower:
            return True
        # Timing qualifier " in advance" does not need to appear in activity name (e.g. "Procure materials" evidences "procure in advance").
        if " in advance" in component or component.endswith(" in advance"):
            core = component.replace(" in advance", "").strip()
            if core:
                if self._activity_covers_component(activity_name_lower, core):
                    return True
                # Multi-word core (e.g. "select procure"): any one action evidences the phrase (e.g. "Procure materials" covers "select procure in advance").
                core_words = [w for w in core.split() if len(w) >= 3]
                def _activity_contains_action(word: str) -> bool:
                    if word in activity_name_lower:
                        return True
                    if word == "procure" and "procurement" in activity_name_lower:
                        return True
                    if word == "procurement" and "procure" in activity_name_lower:
                        return True
                    return False
                if len(core_words) >= 2 and any(_activity_contains_action(w) for w in core_words):
                    return True
        words = [w for w in component.split() if len(w) >= 3]
        if not words:
            return component.strip() in activity_name_lower
        return all(w in activity_name_lower for w in words)

    # Advisory/qualifying component phrases: alignment can be "implicit" if dominant is covered and rest are advisory.
    _ADVISORY_COMPONENT_PATTERNS = (
        "provide advice", "advice", "consider", "inform", "notify", "advise", "review", "comment",
        "consult", "discuss", "liaise", "coordinate",
        "including when", "when instructed", "instructed by", "as directed", "if instructed",
    )

    def _is_advisory_component(self, component: str) -> bool:
        """True if this component is advisory/qualifying (e.g. 'provide advice', 'consider')."""
        if not component or not component.strip():
            return False
        lower = component.strip().lower()
        return any(phrase in lower for phrase in self._ADVISORY_COMPONENT_PATTERNS)

    def _dominant_component(self, components: List[str]) -> str:
        """First non-advisory component, or first component if all advisory."""
        for c in components:
            if c and not self._is_advisory_component(c):
                return c
        return components[0] if components else ""

    def _is_activity_sufficient_for_programme_obligation(self, activity_name: str) -> bool:
        """Programme obligation evidence: activity must show explicit presence (submission, inspection, documentation)."""
        if not activity_name or not activity_name.strip():
            return False
        name = activity_name.strip()
        if _GENERIC_VERB_ONLY.match(name):
            return False
        return bool(_PROGRAMME_OBLIGATION_KEYWORDS.search(name)) or len(name.split()) >= 2

    def _is_activity_generic_for_evidence(self, activity_name_lower: str) -> bool:
        """True if activity is a generic type (inspection, milestone, completion doc, governance review) that cannot evidence unrelated scope."""
        if not activity_name_lower:
            return False
        return any(p.search(activity_name_lower) for p in _GENERIC_EVIDENCE_PATTERNS)

    def _scope_explicitly_requires_generic_type(self, scope_text_lower: str, activity_name_lower: str) -> bool:
        """True if scope item explicitly requires the same generic type as the activity (e.g. 'inspection of X' and activity 'Inspection')."""
        if not scope_text_lower or not activity_name_lower:
            return False
        for p in _GENERIC_EVIDENCE_PATTERNS:
            m = p.search(activity_name_lower)
            if m:
                keyword = m.group(0).strip()
                first_word = keyword.split()[0] if keyword else ""
                if keyword in scope_text_lower or (first_word and first_word in scope_text_lower):
                    return True
        return False

    def _is_valid_evidence_for_action_required_scope(self, scope_text_lower: str, activity_name_lower: str) -> bool:
        """
        For ACTION_REQUIRED scope: evidence must perform the action or produce the deliverable.
        Generic activities (inspection, milestone, completion doc, governance review) are NOT valid
        unless the scope explicitly requires that type.
        """
        if scope_text_lower not in activity_name_lower:
            return False
        if not self._is_activity_generic_for_evidence(activity_name_lower):
            return True
        return self._scope_explicitly_requires_generic_type(scope_text_lower, activity_name_lower)

    def _validate_obligation_entities(
        self,
        contract_data: Dict[str, Any],
        programme_summary: Dict[str, Any],
        activities: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Two-stage obligation-alignment flow. Stage 1: For each obligation determine aligned = True | False
        (programme activities, assurance-based coverage, constraint/governance acknowledgement).
        Acceptability: acceptable iff all mandatory obligations aligned; failure_reasons only from unaligned mandatory.
        Stage 2: Facet outputs (programme, scope, constraints, governance) are diagnostic only; they never add failures.
        """
        entities = contract_data.get("obligation_entities") or {}
        entity_validation_error = entities.get("validation_error") or contract_data.get("obligation_entity_validation_error")
        if entity_validation_error:
            return {
                "status": "fail",
                "obligation_entities_used": True,
                "frozen_used": True,
                "obligations_report": [],
                "programme_obligations": [],
                "scope_evidence_table": [],
                "constraints_control": [],
                "governance_requirements": [],
                "acceptability_failure_reasons": [f"Contract obligation assertion failed: {entity_validation_error}."],
                "requirements": [],
                "total_count": 0,
                "matched_count": 0,
                "missing": [],
                "importance_tier": TIER_1_CRITICAL,
                "outcome": HARD_BREACH,
                "source_clause": "Contract obligations (deduplicated)",
                "source_type": "explicit",
                "validation_basis": "obligation_entities",
                "failure_reason": entity_validation_error,
            }
        obligations_list = entities.get("obligations") or []
        # Intentional: zero mandatory obligations => pass. Not "empty list = success" for existing obligations.
        if not obligations_list:
            return {
                "status": "pass",
                "obligation_entities_used": True,
                "frozen_used": True,
                "obligations_report": [],
                "programme_obligations": [],
                "scope_evidence_table": [],
                "constraints_control": [],
                "governance_requirements": [],
                "acceptability_failure_reasons": [],
                "requirements": [],
                "total_count": 0,
                "matched_count": 0,
                "missing": [],
                "importance_tier": TIER_1_CRITICAL,
                "outcome": COMPLIANT,
                "source_clause": "Contract obligations (deduplicated)",
                "source_type": "explicit",
                "validation_basis": "obligation_entities",
                "failure_reason": None,
            }

        # (activity_id, name_lower, wbs_path) for evidence and hard-coded rules (e.g. Temporary Works)
        activity_rows: List[tuple] = []
        for act in activities:
            aid = (act.get("id") or act.get("task_id") or "").strip()
            name = (act.get("name") or act.get("task_name") or "").strip()
            wbs_path = (act.get("wbs_path") or "").strip()
            if aid or name:
                activity_rows.append((aid, name.lower(), wbs_path))
        activity_rows.sort(key=lambda x: (x[0] or ""))

        programme_constraint_texts: List[str] = []
        for c in (programme_summary.get("constraints") or []):
            if isinstance(c, dict):
                programme_constraint_texts.append((c.get("name") or c.get("description") or c.get("constraint_type") or str(c)).lower())
            elif isinstance(c, str):
                programme_constraint_texts.append(c.lower())
        programme_constraint_blob = " ".join(programme_constraint_texts)
        has_sequencing = len(programme_summary.get("activities", [])) > 0 and programme_summary.get("total_logic_relationships", 0) > 0

        # ESE / appraisal: governance, advisory, register-based, engagement obligations satisfied by assurance unless explicitly contradicted.
        stage_info = _determine_programme_stage(contract_data, programme_summary, activities)
        is_ese_appraisal = (stage_info.get("stage") == "DESIGN_STAGE")

        # -------------------------------------------------------------------------
        # ACCEPTABILITY INVARIANT (see backend/ACCEPTABILITY_INVARIANT.md).
        # WHEN obligation_entities_used == True:
        #   Programme is ACCEPTABLE ⇔ EVERY mandatory obligation has aligned == True.
        #   aligned = True only when: evidenced_by_activities OR acknowledged OR explicit_assumption in {client_responsibility, out_of_scope_at_this_stage}.
        #   explicit_assumption == "covered_by_later_submission" does NOT set aligned; it is advisory only and must block acceptability if mandatory.
        #   Obligation alignment is the only authority; no scores, confidence, narrative, or PCM may affect acceptability.
        # -------------------------------------------------------------------------
        EXPLICIT_ASSUMPTION_VALUES = frozenset({
            "covered_by_later_submission",
            "client_responsibility",
            "out_of_scope_at_this_stage",
        })
        # Only these count for acceptability. "covered_by_later_submission" is advisory only and must NOT set aligned.
        EXPLICIT_ASSUMPTION_ACCEPTABILITY = frozenset({"client_responsibility", "out_of_scope_at_this_stage"})
        obligations_report: List[Dict[str, Any]] = []
        assurance_items_requiring_confirmation: List[Dict[str, Any]] = []

        for ob in obligations_list:
            ob_id = ob.get("id") or ""
            primary_text = (ob.get("original_contract_text") or (ob.get("original_contract_texts") or [None])[0] or ob.get("text") or "").strip()
            if not primary_text:
                continue
            texts = ob.get("original_contract_texts") or [primary_text]
            clause_refs = ob.get("clause_references") or []
            facets = ob.get("facets") or {}
            mandatory = bool(ob.get("mandatory_for_acceptance"))
            scope_class = ob.get("scope_classification") or SCOPE_CLASSIFICATION_ACTION_REQUIRED
            req_lower = primary_text.lower()

            # Evidence mode: PHRASE | WBS_ONLY | HYBRID. If present but invalid → fail loud (configuration error).
            # See ACCEPTABILITY_INVARIANT.md: obligation semantics are read-only; validator must never infer from text.
            evidence_mode_val = ob.get("evidence_mode")
            if evidence_mode_val is not None and str(evidence_mode_val).strip():
                evidence_mode_raw = str(evidence_mode_val).strip().upper()
                if evidence_mode_raw not in (EVIDENCE_MODE_PHRASE, EVIDENCE_MODE_WBS_ONLY, EVIDENCE_MODE_HYBRID):
                    raise RuntimeError(
                        f"Invalid evidence_mode for obligation {ob_id!r}: {evidence_mode_val!r}. "
                        f"Allowed: PHRASE, WBS_ONLY, HYBRID."
                    )
                evidence_mode = evidence_mode_raw
            else:
                evidence_mode = EVIDENCE_MODE_PHRASE

            # WBS_ONLY requires canonical_match_string at construction; no inference from text.
            if evidence_mode == EVIDENCE_MODE_WBS_ONLY:
                cms = ob.get("canonical_match_string")
                if cms is None or not str(cms).strip():
                    raise RuntimeError(
                        f"Obligation {ob_id!r} has evidence_mode=WBS_ONLY but no canonical_match_string. "
                        "WBS_ONLY obligations must be configured with canonical_match_string at construction."
                    )

            # WBS_ONLY: evidence only if canonical_match_string in activity name or WBS path. No phrase, no component, no LLM.
            if evidence_mode == EVIDENCE_MODE_WBS_ONLY:
                search_str = ob.get("canonical_match_string")
                if search_str is None or (isinstance(search_str, str) and not search_str.strip()):
                    search_str = (primary_text or ob.get("canonical_name") or "").strip().lower()
                else:
                    search_str = str(search_str).strip().lower()
                evidence_phrases = []
                evidence_ids = []
                evidenced_by_activities = False
                evidence_method = "wbs_only"
                components = []
                covered = set()
                all_components_covered = False
                dominant_covered_rest_advisory = False
                phrase_evidence_detected = False  # WBS_ONLY path never runs phrase/component/LLM
                ids_in_name: Set[str] = set()
                ids_in_wbs: Set[str] = set()
                if search_str:
                    ids_in_name = {aid for aid, name_lower, _ in activity_rows if search_str in (name_lower or "")}
                    ids_in_wbs = {aid for aid, _, wbs in activity_rows if search_str in (wbs or "").lower()}
                    any_wbs_evidence = ids_in_name or ids_in_wbs
                    evidenced_by_activities = bool(any_wbs_evidence)
                    evidence_ids = list(ids_in_name | ids_in_wbs)[:20] if any_wbs_evidence else []
                if search_str and (ids_in_name or ids_in_wbs) and not evidenced_by_activities:
                    raise RuntimeError(
                        "FATAL: WBS_ONLY obligation has programme evidence (name or WBS) but evidenced_by_activities is False. "
                        f"obligation_id={ob_id}, primary_text={primary_text!r}, evidence_mode={evidence_mode}"
                    )
            elif evidence_mode == EVIDENCE_MODE_HYBRID:
                # Phrase logic first; if not evidenced, also check name/WBS for obligation text.
                evidence_phrases = self._extract_evidence_phrases(primary_text)
                evidence_ids = []
                evidenced_by_activities = False
                evidence_method = "phrase"
                use_llm_evidence = os.environ.get("USE_LLM_OBLIGATION_EVIDENCE", "").strip().lower() in ("1", "true", "yes")
                if use_llm_evidence:
                    try:
                        from app.p6_engine.validation_ai_review import evaluate_obligation_evidence_llm
                        activity_rows_id_name = [(r[0], r[1]) for r in activity_rows]
                        evidenced_llm, ids_llm = evaluate_obligation_evidence_llm(primary_text, activity_rows_id_name)
                        if evidenced_llm and ids_llm:
                            evidence_ids = ids_llm
                            evidenced_by_activities = True
                            evidence_method = "llm"
                    except Exception:
                        pass
                if not evidenced_by_activities:
                    for act_id, name_lower, _ in activity_rows:
                        if self._phrase_evidences_obligation(name_lower, evidence_phrases):
                            evidence_ids.append(act_id)
                    evidenced_by_activities = len(evidence_ids) > 0
                if not evidenced_by_activities:
                    search_str = ob.get("canonical_match_string") or (primary_text or ob.get("canonical_name") or "").strip().lower()
                    if isinstance(search_str, str) and search_str.strip():
                        search_str = search_str.strip().lower()
                        ids_in_name = {aid for aid, name_lower, _ in activity_rows if search_str in (name_lower or "")}
                        ids_in_wbs = {aid for aid, _, wbs in activity_rows if search_str in (wbs or "").lower()}
                        if ids_in_name or ids_in_wbs:
                            evidenced_by_activities = True
                            evidence_ids = list(ids_in_name | ids_in_wbs)[:20]
                            evidence_method = "hybrid"
                phrase_evidence_detected = evidence_method in ("phrase", "llm")
                components = self._extract_obligation_action_components(primary_text)
                covered = set()
                if evidence_phrases and evidence_ids:
                    for _, name_lower, _ in activity_rows:
                        for comp in components:
                            if comp not in covered and self._activity_covers_component(name_lower, comp):
                                covered.add(comp)
                all_components_covered = len(covered) == len(components) if components else False
                dominant_covered_rest_advisory = False
                if not all_components_covered and components:
                    dominant = self._dominant_component(components)
                    uncovered = [c for c in components if c not in covered]
                    dominant_covered = (dominant in covered) or any(
                        self._activity_covers_component(name_lower, dominant)
                        for _, name_lower, _ in activity_rows
                    )
                    if dominant_covered and uncovered and all(self._is_advisory_component(c) for c in uncovered):
                        dominant_covered_rest_advisory = True
                if not evidenced_by_activities and (all_components_covered or (len(components) >= 2 and dominant_covered_rest_advisory)):
                    evidenced_by_activities = True
                    if not evidence_ids:
                        for act_id, name_lower, _ in activity_rows:
                            for comp in components:
                                if self._activity_covers_component(name_lower, comp):
                                    evidence_ids.append(act_id)
                                    break
                            if evidence_ids:
                                break
            else:
                # PHRASE (default): optional LLM or phrase-based + component coverage.
                evidence_phrases = self._extract_evidence_phrases(primary_text)
                evidence_ids = []
                evidenced_by_activities = False
                evidence_method = "phrase"
                use_llm_evidence = os.environ.get("USE_LLM_OBLIGATION_EVIDENCE", "").strip().lower() in ("1", "true", "yes")
                if use_llm_evidence:
                    try:
                        from app.p6_engine.validation_ai_review import evaluate_obligation_evidence_llm
                        activity_rows_id_name = [(r[0], r[1]) for r in activity_rows]
                        evidenced_llm, ids_llm = evaluate_obligation_evidence_llm(primary_text, activity_rows_id_name)
                        if evidenced_llm and ids_llm:
                            evidence_ids = ids_llm
                            evidenced_by_activities = True
                            evidence_method = "llm"
                    except Exception:
                        pass
                if not evidenced_by_activities:
                    for act_id, name_lower, _ in activity_rows:
                        if self._phrase_evidences_obligation(name_lower, evidence_phrases):
                            evidence_ids.append(act_id)
                    evidenced_by_activities = len(evidence_ids) > 0
                phrase_evidence_detected = True  # PHRASE path always uses phrase/component/LLM
                components = self._extract_obligation_action_components(primary_text)
                covered = set()
                if evidence_phrases and evidence_ids:
                    for _, name_lower, _ in activity_rows:
                        for comp in components:
                            if comp not in covered and self._activity_covers_component(name_lower, comp):
                                covered.add(comp)
                all_components_covered = len(covered) == len(components) if components else False
                dominant_covered_rest_advisory = False
                if not all_components_covered and components:
                    dominant = self._dominant_component(components)
                    uncovered = [c for c in components if c not in covered]
                    dominant_covered = (dominant in covered) or any(
                        self._activity_covers_component(name_lower, dominant)
                        for _, name_lower, _ in activity_rows
                    )
                    if dominant_covered and uncovered and all(self._is_advisory_component(c) for c in uncovered):
                        dominant_covered_rest_advisory = True
                if not evidenced_by_activities and (all_components_covered or (len(components) >= 2 and dominant_covered_rest_advisory)):
                    evidenced_by_activities = True
                    if not evidence_ids:
                        for act_id, name_lower, _ in activity_rows:
                            for comp in components:
                                if self._activity_covers_component(name_lower, comp):
                                    evidence_ids.append(act_id)
                                    break
                            if evidence_ids:
                                break

            # Guard: WBS_ONLY must never be satisfied by phrase/component/LLM evidence.
            if evidence_mode == EVIDENCE_MODE_WBS_ONLY and phrase_evidence_detected:
                raise RuntimeError(
                    "ILLEGAL: Phrase evidence applied to WBS_ONLY obligation. "
                    f"obligation_id={ob_id}, primary_text={primary_text!r}"
                )

            # ---- Acknowledged (constraints / sequencing) ----
            acknowledged = False
            if facets.get("has_timing_requirement") or facets.get("has_governance_requirement"):
                words = [w for w in req_lower.split() if len(w) > 2][:5]
                if programme_constraint_blob and words and any(w in programme_constraint_blob for w in words):
                    acknowledged = True
                if has_sequencing and not acknowledged:
                    acknowledged = True

            # ---- Assurance-based: diagnostic only; MUST NOT set aligned (evidence-first policy) ----
            assurance_based = (
                (scope_class == SCOPE_CLASSIFICATION_ASSURANCE_REQUIRED and facets.get("has_scope_component"))
                or (facets.get("has_scope_component") and _is_advisory_design_text(primary_text))
                or facets.get("has_governance_requirement")
                or _is_advisory_governance_coordination_text(primary_text)
            )
            if is_ese_appraisal and _is_ese_assurance_obligation(primary_text, facets):
                assurance_based = True

            # ---- ALIGNMENT (ACCEPTABILITY_INVARIANT.md): aligned only if evidence satisfies evidence_mode, or acknowledged, or explicit_assumption in {client_responsibility, out_of_scope_at_this_stage}. Acknowledgement/assurance must NOT override WBS_ONLY. ----
            # covered_by_later_submission is advisory only and must NOT set aligned; mandatory with only this remain not aligned and block acceptability.
            explicit_assumption = (ob.get("explicit_assumption") or "").strip().lower()
            if explicit_assumption not in EXPLICIT_ASSUMPTION_VALUES:
                explicit_assumption = None
            if explicit_assumption:
                explicit_assumption_label = {
                    "covered_by_later_submission": "Assumed to be covered by later submission",
                    "client_responsibility": "Client responsibility",
                    "out_of_scope_at_this_stage": "Out of scope at this stage",
                }.get(explicit_assumption, explicit_assumption)

            aligned = evidenced_by_activities or acknowledged or (explicit_assumption in EXPLICIT_ASSUMPTION_ACCEPTABILITY)
            # Mandatory + WBS_ONLY: alignment only via WBS/name evidence. Acknowledgement/assurance must never set aligned.
            if mandatory and evidence_mode == EVIDENCE_MODE_WBS_ONLY:
                aligned = bool(evidenced_by_activities)
            alignment_basis: Optional[str] = None
            exemption_reason: Optional[str] = None
            if evidenced_by_activities:
                alignment_basis = "evidenced_by_activities"
            elif acknowledged:
                alignment_basis = "acknowledged"
            elif explicit_assumption and explicit_assumption in EXPLICIT_ASSUMPTION_ACCEPTABILITY:
                alignment_basis = "explicit_assumption"
                exemption_reason = explicit_assumption_label
            elif explicit_assumption == "covered_by_later_submission":
                alignment_basis = "covered_by_later_submission"
                exemption_reason = explicit_assumption_label

            # Alignment strength / label for reporting.
            if not aligned:
                alignment_strength = "not aligned"
            elif alignment_basis == "explicit_assumption":
                alignment_strength = "explicit_assumption"
            elif alignment_basis == "covered_by_later_submission":
                alignment_strength = "not aligned"
            elif evidenced_by_activities and all_components_covered:
                alignment_strength = "explicit"
            elif evidenced_by_activities:
                alignment_strength = "explicit" if not (len(components) >= 2 and dominant_covered_rest_advisory) else "implicit"
            elif acknowledged:
                alignment_strength = "implicit"
            else:
                alignment_strength = "not aligned"

            # Assurance-based: NEVER count as evidence; surface only under "Requires governance / future submission". Must not justify acceptance.
            if assurance_based:
                assurance_items_requiring_confirmation.append({
                    "id": ob_id,
                    "original_contract_text": primary_text,
                    "note": "Requires governance / future submission.",
                })

            # "Not represented but mandatory" = mandatory and not aligned (includes covered_by_later_submission-only; that assumption does not count for acceptability).
            not_represented_but_mandatory = mandatory and not aligned

            # Required action (presentation only): what to add to the programme to pass. Does not affect alignment or acceptability.
            canonical_match_string = ob.get("canonical_match_string") or primary_text.strip().lower()
            if not aligned and mandatory:
                if evidence_mode == EVIDENCE_MODE_WBS_ONLY:
                    required_action = f"Add at least one activity under a WBS or activity name containing '{canonical_match_string}'"
                elif evidence_mode == EVIDENCE_MODE_PHRASE:
                    required_action = f"Add an activity explicitly covering \"{primary_text}\""
                elif evidence_mode == EVIDENCE_MODE_HYBRID:
                    required_action = f"Add phrase evidence or a WBS/activity name containing '{canonical_match_string}'"
                else:
                    required_action = f"Add an activity explicitly covering \"{primary_text}\""
            else:
                required_action = None

            clause_ref = clause_refs[0] if clause_refs else ""
            obligations_report.append({
                "id": ob_id,
                "original_contract_text": primary_text,
                "original_contract_texts": texts,
                "canonical_name": ob.get("canonical_name"),
                "canonical_match_string": ob.get("canonical_match_string"),
                "clause_references": clause_refs,
                "clause_reference": clause_ref,
                "facets": facets,
                "scope_classification": scope_class if facets.get("has_scope_component") else None,
                "mandatory_for_acceptance": mandatory,
                "evidenced_by_activities": evidenced_by_activities,
                "evidenced": evidenced_by_activities,
                "evidence_activity_ids": evidence_ids,
                "evidence_mode": ob.get("evidence_mode"),
                "required_action": required_action,
                "acknowledged": acknowledged,
                "assurance_based": assurance_based,
                "aligned": aligned,
                "alignment_basis": alignment_basis,
                "exemption_reason": exemption_reason,
                "explicit_assumption": explicit_assumption,
                "not_represented_but_mandatory": not_represented_but_mandatory,
                "alignment_strength": alignment_strength,
                "action_components": components,
                "covered_components": list(covered),
                "evidence_phrases": evidence_phrases,
                "evidence_method": evidence_method,
                "coverage_status": "Aligned" if aligned else "Pending",
            })

        # Safety: aligned only from evidenced, acknowledged, or explicit_assumption in {client_responsibility, out_of_scope_at_this_stage}.
        for r in obligations_report:
            exp = (r.get("explicit_assumption") or "").strip().lower()
            counts_for_acceptability = exp in ("client_responsibility", "out_of_scope_at_this_stage")
            if not r.get("evidenced_by_activities") and not r.get("acknowledged") and not counts_for_acceptability:
                if r.get("aligned"):
                    r["aligned"] = False
                    r["alignment_basis"] = "covered_by_later_submission" if exp == "covered_by_later_submission" else None
                    if exp != "covered_by_later_submission":
                        r["exemption_reason"] = None
                    r["alignment_strength"] = "not aligned"
                    r["coverage_status"] = "Pending"
                    logger.warning("Obligation %s was aligned without evidence/ack/acceptability-counting explicit_assumption; forced to not aligned.", r.get("id"))
        # HARD GUARD: assurance_based must NEVER set aligned.
        for r in obligations_report:
            exp = (r.get("explicit_assumption") or "").strip().lower()
            counts = exp in ("client_responsibility", "out_of_scope_at_this_stage")
            if r.get("assurance_based") and r.get("aligned") and not (
                r.get("evidenced_by_activities") or r.get("acknowledged") or counts
            ):
                raise RuntimeError(
                    "Contradiction: obligation has assurance_based=True and aligned=True without evidence, acknowledgement, or explicit assumption. "
                    f"Obligation ID: {r.get('id')}. Assurance-based must never set aligned or justify acceptance."
                )

        # Mandatory and not aligned => fail. Assurance ≠ evidence: assurance_based NEVER sets aligned; if mandatory and not evidenced/ack/explicit_assumption, fail even if assurance-based.
        ids_that_may_fail: Set[str] = {
            r["id"] for r in obligations_report
            if r.get("mandatory_for_acceptance") and not r.get("aligned")
        }
        failure_reasons = []
        failure_ob_ids: Set[str] = set()
        for r in obligations_report:
            if r["id"] not in ids_that_may_fail:
                continue
            orig = r.get("original_contract_text", "")
            if (r.get("explicit_assumption") or "").strip().lower() == "covered_by_later_submission":
                msg = (
                    f"Mandatory obligation not represented in the programme: \"{orig[:50]}...\" (id: {r['id']}). "
                    "'Covered by later submission' is not sufficient for acceptance."
                ) if len(orig) > 50 else (
                    f"Mandatory obligation not represented in the programme: \"{orig}\" (id: {r['id']}). "
                    "'Covered by later submission' is not sufficient for acceptance."
                )
            else:
                msg = (
                    f"Not represented but mandatory: \"{orig[:50]}...\" (id: {r['id']}). "
                    "Require either explicit programme activities or an explicit assumption (client responsibility / out of scope at this stage)."
                ) if len(orig) > 50 else (
                    f"Not represented but mandatory: \"{orig}\" (id: {r['id']}). "
                    "Require either explicit programme activities or an explicit assumption."
                )
            failure_reasons.append(msg)
            failure_ob_ids.add(r["id"])
            logger.debug({
                "obligation_id": r["id"],
                "mandatory": r.get("mandatory_for_acceptance"),
                "evidenced_by_activities": r.get("evidenced_by_activities"),
                "acknowledged": r.get("acknowledged"),
                "alignment_basis": r.get("alignment_basis"),
                "aligned": r.get("aligned"),
                "alignment_strength": r.get("alignment_strength"),
                "components": r.get("action_components"),
                "covered_components": r.get("covered_components"),
            })

        # HARD SAFETY INVARIANT: no obligation may be both aligned and in the failure set.
        aligned_ob_ids = {r["id"] for r in obligations_report if r.get("aligned") is True}
        contradiction = aligned_ob_ids & failure_ob_ids
        if contradiction:
            raise RuntimeError(
                "Contradiction: obligation(s) both aligned and in failure set. "
                "Aligned may only come from evidenced, acknowledged, or explicit_assumption. IDs: " + ", ".join(contradiction)
            )

        # SINGLE ACCEPTABILITY GATE (ACCEPTABILITY_INVARIANT.md): status and acceptability are determined only here. No legacy engines, no scores, no report-layer inference. No other path may set pass/ACCEPTABLE when obligation_entities_used. The acceptability engine is frozen; do not modify without updating invariants and tests.
        status = "fail" if failure_reasons else "pass"
        outcome = HARD_BREACH if status == "fail" else COMPLIANT
        aligned_count = sum(1 for r in obligations_report if r.get("aligned"))

        # -------------------------------------------------------------------------
        # CONTRADICTION TRIPWIRES (must crash; block report if violated)
        # -------------------------------------------------------------------------
        not_rep_mandatory_ids = [r["id"] for r in obligations_report if r.get("not_represented_but_mandatory")]
        if not_rep_mandatory_ids and status == "pass":
            logger.error("CONTRADICTION: not_represented_but_mandatory obligations exist but status=pass. IDs: %s", not_rep_mandatory_ids)
            raise RuntimeError(
                "Acceptability contradiction: mandatory obligations not represented but programme marked pass. "
                "not_represented_but_mandatory obligation IDs: " + ", ".join(not_rep_mandatory_ids)
            )
        for r in obligations_report:
            if r.get("aligned") and r.get("not_represented_but_mandatory"):
                logger.error("CONTRADICTION: obligation %s is both aligned and not_represented_but_mandatory", r.get("id"))
                raise RuntimeError(
                    f"Obligation {r.get('id')} cannot be both aligned and not_represented_but_mandatory."
                )
        # If status is pass, every mandatory obligation must be evidenced, acknowledged, or explicit_assumption.
        if status == "pass":
            for r in obligations_report:
                if r.get("mandatory_for_acceptance") and not r.get("aligned"):
                    logger.error("CONTRADICTION: programme pass but mandatory obligation %s not aligned", r.get("id"))
                    raise RuntimeError(
                        "Acceptability contradiction: programme marked pass but mandatory obligation not aligned. "
                        f"Obligation ID: {r.get('id')}. Every mandatory must be evidenced, acknowledged, or explicit_assumption."
                    )

        # -------------------------------------------------------------------------
        # STAGE 2 – EVIDENCE EXPLANATION (Diagnostic Only)
        # alignment_strength, represented/not represented, scope facet tables are diagnostic-only.
        # They must NEVER influence acceptability. diagnostic_only = True; note = exact text below.
        # -------------------------------------------------------------------------
        _diagnostic_note = "Descriptive only; does not affect acceptability."
        programme_obligations_report = [
            {**r, "obligation_type": "programme_obligation", "diagnostic_only": True, "note": _diagnostic_note}
            for r in obligations_report
            if (r.get("facets") or {}).get("has_programme_duty")
        ]
        def _representation_status(ob: Dict[str, Any]) -> str:
            if ob.get("evidenced_by_activities"):
                return "evidenced"
            if ob.get("acknowledged"):
                return "acknowledged"
            if ob.get("assurance_based"):
                return "assurance_based"  # Surfaces as "Requires governance / future submission"
            if (ob.get("explicit_assumption") or "").strip().lower() == "covered_by_later_submission":
                return "covered_by_later_submission"  # Advisory only; does not set aligned
            if ob.get("alignment_basis") == "explicit_assumption":
                return "explicit_assumption"
            if ob.get("not_represented_but_mandatory"):
                return "not_represented_but_mandatory"
            return "not_represented"

        def _representation_status_label(status: str) -> str:
            if status == "assurance_based":
                return "Requires governance / future submission"
            if status == "not_represented_but_mandatory":
                return "Not represented but mandatory"
            if status == "covered_by_later_submission":
                return "Obligations assumed to be covered by later submission (non-blocking advisory only)"
            if status == "explicit_assumption":
                return "Explicit assumption"
            return status.replace("_", " ").title()

        scope_evidence_table = [
            {
                **r,
                "text": r.get("original_contract_text", ""),
                "obligation_type": "scope_obligation",
                "acceptability_impact": "none",
                "diagnostic_only": True,
                "note": _diagnostic_note,
                "representation_status": _representation_status(r),
                "representation_status_label": _representation_status_label(_representation_status(r)),
                "evidence_sufficient_reason": (
                    f"Aligned; explained by {len(r.get('evidence_activity_ids', []))} programme activity/activities."
                    if r.get("evidenced_by_activities") else (
                        f"Aligned; {r.get('exemption_reason', '')}" if r.get("alignment_basis") == "explicit_assumption" else (
                            "Advisory only; 'covered by later submission' does not justify acceptance." if (r.get("explicit_assumption") or "").strip().lower() == "covered_by_later_submission" else (
                                "Requires governance / future submission." if r.get("assurance_based") else ""
                            )
                        )
                    )
                ),
            }
            for r in obligations_report
            if (r.get("facets") or {}).get("has_scope_component")
        ]
        # Safety: not_represented_but_mandatory must not be aligned (no silent exemptions).
        for s in scope_evidence_table:
            if s.get("representation_status") == "not_represented_but_mandatory" and s.get("aligned"):
                raise ValueError("Safety: obligation Not represented but mandatory must not be aligned without explicit_assumption.")

        constraints_control = [
            {
                **r,
                "obligation_type": "constraint",
                "diagnostic_only": True,
                "note": _diagnostic_note,
                "how_controlled": (
                    "Aligned; evidenced in programme constraints or sequencing."
                    if r.get("acknowledged") else ""
                ),
            }
            for r in obligations_report
            if (r.get("facets") or {}).get("has_timing_requirement")
        ]
        governance_report = [
            {**r, "obligation_type": "governance_requirement", "diagnostic_only": True, "note": _diagnostic_note}
            for r in obligations_report
            if (r.get("facets") or {}).get("has_governance_requirement")
        ]

        obligations_evidenced = [r for r in obligations_report if r.get("evidenced_by_activities")]
        obligations_explicit_assumption = [r for r in obligations_report if r.get("alignment_basis") == "explicit_assumption"]
        obligations_covered_by_later_submission = [r for r in obligations_report if (r.get("explicit_assumption") or "").strip().lower() == "covered_by_later_submission"]
        obligations_not_represented_but_mandatory = [r for r in obligations_report if r.get("not_represented_but_mandatory")]
        obligations_assurance_based = [r for r in obligations_report if r.get("assurance_based")]

        result: Dict[str, Any] = {
            "status": status,
            "obligation_entities_used": True,
            "frozen_used": True,
            "alignment_basis": "obligation_alignment",
            "alignment_note": (
                "aligned = evidenced OR acknowledged OR explicit_assumption in {client_responsibility, out_of_scope_at_this_stage}. "
                "'Covered by later submission' is advisory only and does NOT set aligned; mandatory with only this assumption block acceptability. "
                "Assurance-based is NOT evidence. acceptable = all mandatory obligations aligned."
            ),
            "obligations_report": obligations_report,
            "obligations_evidenced": obligations_evidenced,
            "obligations_explicit_assumption": obligations_explicit_assumption,
            "obligations_covered_by_later_submission": obligations_covered_by_later_submission,
            "obligations_not_represented_but_mandatory": obligations_not_represented_but_mandatory,
            "obligations_assurance_based": obligations_assurance_based,
            "programme_obligations": programme_obligations_report,
            "programme_obligations_diagnostic_only": True,
            "scope_evidence_table": scope_evidence_table,
            "scope_evidence_table_diagnostic_only": True,
            "scope_items_total": len(scope_evidence_table),
            "scope_items_matched": sum(1 for s in scope_evidence_table if s.get("aligned")),
            "scope_items_missing": len(scope_evidence_table) - sum(1 for s in scope_evidence_table if s.get("aligned")),
            "scope_items_unevidenced": sum(1 for s in scope_evidence_table if not s.get("aligned")),
            "constraints_control": constraints_control,
            "constraints_control_diagnostic_only": True,
            "constraints_total": len(constraints_control),
            "constraints_unacknowledged": sum(1 for c in constraints_control if not c.get("acknowledged")),
            "governance_requirements": governance_report,
            "governance_requirements_diagnostic_only": True,
            "governance_total": len(governance_report),
            "governance_missing": sum(1 for g in governance_report if not g.get("aligned")),
            "acceptability_failure_reasons": failure_reasons,
            "assurance_items_requiring_confirmation": assurance_items_requiring_confirmation,
            "scope_acceptability_failures_count": len(failure_reasons),
            "requirements": [
                {"id": r["id"], "original_contract_text": r.get("original_contract_text", ""), "matched": r.get("aligned"), "evidence": r.get("evidence_activity_ids", [])}
                for r in obligations_report
            ],
            "total_count": len(obligations_report),
            "matched_count": aligned_count,
            "aligned_count": aligned_count,
            "missing": failure_reasons,
            "importance_tier": TIER_1_CRITICAL,
            "outcome": outcome,
            "source_clause": "Contract obligations (deduplicated)",
            "source_type": "explicit",
            "validation_basis": "obligation_entities",
            "failure_reason": "; ".join(failure_reasons[:10]) + (" ..." if len(failure_reasons) > 10 else "") if failure_reasons else None,
        }
        return result

    def _validate_against_frozen_requirements(
        self,
        contract_data: Dict[str, Any],
        programme_summary: Dict[str, Any],
        activities: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Deterministic validation against the frozen requirement list only.
        No re-interpretation: each requirement maps to explicit programme activity IDs or matched=false.
        Acceptability: NOT ACCEPTABLE if any requirement has matched=false.
        Evidence arrays are never empty when matched=true.
        """
        frozen_list = contract_data.get("frozen_requirements") or []
        if not isinstance(frozen_list, list):
            frozen_list = []

        # Programme activities: stable (id, name_lower) sorted by id for determinism
        activity_rows: List[tuple] = []
        for act in activities:
            aid = (act.get("id") or act.get("task_id") or "").strip()
            name = (act.get("name") or act.get("task_name") or "").strip()
            if aid or name:
                activity_rows.append((aid, name.lower()))
        activity_rows.sort(key=lambda x: (x[0] or ""))

        requirements_out: List[Dict[str, Any]] = []
        missing: List[str] = []
        missing_ids: List[str] = []

        for req in frozen_list:
            if not isinstance(req, dict):
                continue
            req_id = req.get("id") or ""
            req_type = req.get("type") or "scope"
            req_text = (req.get("original_contract_text") or req.get("text") or "").strip()
            if not req_text and (req.get("original_contract_texts") or []):
                req_text = (req["original_contract_texts"][0] or "").strip()
            if not req_text:
                continue
            req_lower = req_text.lower()
            # Strict: requirement text must appear as substring in activity name (no proxies, no implied coverage)
            evidence_ids: List[str] = []
            for act_id, name_lower in activity_rows:
                if not name_lower:
                    continue
                if req_lower in name_lower:
                    evidence_ids.append(act_id)
            matched = len(evidence_ids) > 0
            if not matched:
                missing.append(req_text)
                missing_ids.append(req_id)
            requirements_out.append({
                "id": req_id,
                "type": req_type,
                "text": req_text,
                "matched": matched,
                "evidence": evidence_ids,
            })

        n_total = len(requirements_out)
        n_matched = sum(1 for r in requirements_out if r["matched"])
        n_missing = n_total - n_matched
        status = "pass" if n_missing == 0 else "fail"
        outcome = COMPLIANT if status == "pass" else HARD_BREACH

        result: Dict[str, Any] = {
            "status": status,
            "frozen_used": True,
            "requirements": requirements_out,
            "total_count": n_total,
            "matched_count": n_matched,
            "unmatched_count": n_missing,
            "scope_items_total": n_total,
            "scope_items_matched": n_matched,
            "scope_items_missing": n_missing,
            "missing": missing,
            "missing_ids": missing_ids,
            "summary": (
                f"Frozen requirements: {n_total}. Matched: {n_matched}/{n_total}. "
                + (f"Unmatched: {n_missing}." if n_missing else "All matched.")
            ),
            "importance_tier": TIER_1_CRITICAL,
            "outcome": outcome,
            "source_clause": "Contract scope / constraints / administrative requirements (primary obligations)",
            "source_type": "explicit",
            "validation_basis": "frozen_requirements",
        }
        if status == "fail":
            result["failure_reason"] = (
                "One or more mandatory obligations are not evidenced. "
                + "Missing (by id): " + ", ".join(missing_ids[:20]) + (" ..." if len(missing_ids) > 20 else "")
            )
        return result

    def _validate_scope_coverage(
        self,
        contract_data: Dict[str, Any],
        programme_summary: Dict[str, Any],
        activity_names_lower: List[str],
        activities: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Legacy: scope items, required activities, constraints (when frozen_requirements not present).
        MUST NOT run when obligation_entities are present; scope_coverage is set by _validate_obligation_entities only.
        """
        # Tripwire: if obligation entities exist, this legacy engine must never run.
        obligation_entities = contract_data.get("obligation_entities") or {}
        obligations_list = obligation_entities.get("obligations") if isinstance(obligation_entities, dict) else None
        if isinstance(obligations_list, list) and len(obligations_list) > 0:
            raise RuntimeError(
                "Ghost engine: _validate_scope_coverage must not run when contract has obligation_entities. "
                "Scope and constraints must be derived only from _validate_obligation_entities."
            )

        def _normalize_to_strings(items: Any) -> List[str]:
            out: List[str] = []
            for item in (items or []):
                if isinstance(item, str):
                    t = item.strip()
                elif isinstance(item, dict):
                    t = (
                        item.get("text") or item.get("value") or item.get("description")
                        or item.get("name") or item.get("requirement") or item.get("content") or ""
                    )
                    if not t and isinstance(item.get("features"), dict):
                        f = item["features"]
                        t = f.get("description") or ""
                        if not t:
                            for key in ("actions", "assets", "discipline"):
                                val = f.get(key)
                                if isinstance(val, str) and val.strip():
                                    t = t or val
                                    break
                                if isinstance(val, list) and val:
                                    t = " ".join(str(v) for v in val[:5] if v)
                                    break
                    t = (t if isinstance(t, str) else str(t)).strip()
                else:
                    t = str(item).strip() if item else ""
                if t:
                    out.append(t)
            return out

        # Contract may have scope_items at top level (analyze_contract output) or nested
        raw_scope = contract_data.get("scope_items", []) or contract_data.get("scope_items_list", []) or []
        if not raw_scope and isinstance(contract_data.get("metadata"), dict):
            raw_scope = contract_data.get("metadata", {}).get("scope_items", []) or []
        pcm = contract_data.get("programme_compliance_model", {}) or {}
        raw_required = pcm.get("required_activities", []) or []
        raw_constraints = contract_data.get("constraints", []) or []
        raw_seq_constraints = pcm.get("sequencing_and_timing_constraints", []) or []

        scope_texts = _normalize_to_strings(raw_scope)
        required_texts = _normalize_to_strings(raw_required)
        constraint_texts = _normalize_to_strings(raw_constraints) + _normalize_to_strings(raw_seq_constraints)

        # Unified list: (text, type) — same concept for all: missing = fail
        seen_lower: Set[str] = set()
        all_items: List[tuple] = []  # (text, "scope_item" | "required_activity" | "constraint")
        for t in scope_texts:
            key = t.lower().strip()
            if key and key not in seen_lower:
                seen_lower.add(key)
                all_items.append((t, "scope_item"))
        for t in required_texts:
            key = t.lower().strip()
            if key and key not in seen_lower:
                seen_lower.add(key)
                all_items.append((t, "required_activity"))
        for t in constraint_texts:
            key = t.lower().strip()
            if key and key not in seen_lower:
                seen_lower.add(key)
                all_items.append((t, "constraint"))

        programme_activity_details: List[Dict[str, Any]] = []
        for activity in activities:
            name = (activity.get("name") or "").strip()
            lower = name.lower()
            programme_activity_details.append({
                "name": name,
                "name_lower": lower,
                "intent": _extract_semantic_intent(name),
            })

        # Programme constraint text for matching (if XER ever provides descriptions)
        programme_constraint_texts: List[str] = []
        for c in (programme_summary.get("constraints") or []):
            if isinstance(c, dict):
                programme_constraint_texts.append((c.get("name") or c.get("description") or c.get("constraint_type") or str(c)).lower())
            elif isinstance(c, str):
                programme_constraint_texts.append(c.lower())
        all_programme_evidence = " ".join(programme_constraint_texts)

        matched: List[str] = []
        missing: List[str] = []
        missing_by_type: Dict[str, List[str]] = {"scope_item": [], "required_activity": [], "constraint": []}
        entries: List[Dict[str, Any]] = []

        for contract_text, item_type in all_items:
            req_lower = contract_text.lower()
            req_intent = _extract_semantic_intent(contract_text)
            matched_entry: Optional[Dict[str, Any]] = None
            match_basis = "semantic intent"
            match_explanation = ""

            for detail in programme_activity_details:
                name_lower = detail["name_lower"]
                if not name_lower:
                    continue
                if req_lower in name_lower or name_lower in req_lower:
                    matched_entry = detail
                    match_basis = "exact"
                    match_explanation = f'Exact text match: appears in programme activity "{detail["name"]}".'
                    break

            if not matched_entry:
                for detail in programme_activity_details:
                    if _semantic_intent_match(req_intent, detail["intent"]):
                        matched_entry = detail
                        match_basis = "semantic intent"
                        shared_actions = sorted(req_intent["actions"] & detail["intent"]["actions"])
                        shared_nouns = sorted(req_intent["nouns"] & detail["intent"]["nouns"])
                        bits = [f"action(s) {', '.join(shared_actions)}" if shared_actions else "", f"noun(s) {', '.join(shared_nouns)}" if shared_nouns else ""]
                        match_explanation = "Semantic intent match: " + (" and ".join(b for b in bits if b) or "overlapping keywords.")
                        break

            if not matched_entry and all_programme_evidence:
                if any(tok in all_programme_evidence for tok in req_lower.split() if len(tok) > 3):
                    match_explanation = "Evidenced in programme constraints."
                    matched_entry = {"name": "(programme constraints)"}

            status = "FOUND" if matched_entry else "NOT_FOUND"
            if matched_entry:
                matched.append(contract_text)
            else:
                missing.append(contract_text)
                missing_by_type[item_type].append(contract_text)

            entries.append({
                "contract_activity": contract_text,
                "scope_item": contract_text,
                "item_type": item_type,
                "status": status,
                "matched_programme_activities": [matched_entry["name"]] if matched_entry else [],
                "matching_basis": match_basis,
                "matching_explanation": match_explanation or ("Not evidenced in programme." if not matched_entry else ""),
            })

        n_total = len(all_items)
        n_missing = len(missing)
        status = "pass" if n_missing == 0 else "fail"
        if n_total == 0:
            summary = "No contract scope items, required activities, or constraints were identified; coverage check not applicable."
        else:
            summary = (
                f"Contract items (scope + required activities + constraints): {n_total}. "
                f"Evidenced in programme: {n_total - n_missing}/{n_total}. "
                + (f"Missing: {n_missing}." if n_missing else "All items evidenced.")
            )

        result: Dict[str, Any] = {
            "status": status,
            "scope_items_total": n_total,
            "contract_activities_total": n_total,
            "scope_items_matched": len(matched),
            "scope_items_missing": n_missing,
            "matched": matched,
            "missing": missing,
            "missing_scope_items": missing_by_type["scope_item"],
            "missing_required_activities": missing_by_type["required_activity"],
            "missing_constraints": missing_by_type["constraint"],
            "entries": entries,
            "summary": summary,
        }
        if status == "fail":
            result["failure_reason"] = "One or more mandatory obligations are not evidenced."
        return result

    def _create_alignment_entry(
        self,
        contract_value: str,
        programme_value: str,
        field_name: str
    ) -> Dict[str, Any]:
        """Create alignment entry with variance calculation."""
        if not contract_value:
            return {
                "contract": "",
                "programme": programme_value if programme_value else "",
                "variance_days": None,
                "status": "contract_missing",
                "reason": f"Contract {field_name} is missing"
            }
        
        if not programme_value:
            return {
                "contract": contract_value,
                "programme": "",
                "variance_days": None,
                "status": "programme_missing",
                "reason": f"Programme {field_name} is missing"
            }
        
        # Try to parse dates and calculate variance
        contract_dt = self._parse_date(contract_value)
        programme_dt = self._parse_date(programme_value)
        
        variance_days = None
        status = "unknown"
        reason = ""
        
        if contract_dt and programme_dt:
            variance_days = (programme_dt - contract_dt).days
            if variance_days == 0:
                status = "aligned"
                reason = "Dates match exactly"
            elif variance_days > 0:
                status = "programme_later"
                reason = f"Programme is {variance_days} days later than contract"
            else:
                status = "programme_earlier"
                reason = f"Programme is {abs(variance_days)} days earlier than contract"
        else:
            # String comparison fallback
            if contract_value == programme_value:
                status = "aligned"
                reason = "Values match (string comparison)"
            else:
                status = "mismatch"
                reason = "Different representations noted (date format or value); see notes for detail."
        
        return {
            "contract": contract_value,
            "programme": programme_value,
            "variance_days": variance_days,
            "status": status,
            "reason": reason
        }

    def _create_completion_alignment_entry(
        self,
        contract_value: str,
        programme_value: str,
        field_name: str,
        programme_uses_5day_workweek: bool = False,
    ) -> Dict[str, Any]:
        """Create completion-date alignment; if programme uses 5-day workweek/worksheet schedule, contract date on
        weekend does not count—programme completing the next working day (e.g. 1 April after 31 March Sunday) is aligned."""
        entry = self._create_alignment_entry(contract_value, programme_value, field_name)
        if not programme_uses_5day_workweek or entry.get("status") != "programme_later":
            return entry
        variance_days = entry.get("variance_days")
        if variance_days is None or variance_days not in (1, 2):
            return entry
        contract_dt = self._parse_date(contract_value)
        if not contract_dt:
            return entry
        # Monday=0, Sunday=6. Contract on Sunday (6) + 1 day = Monday (aligned). Contract on Saturday (5) + 2 days = Monday (aligned).
        if variance_days == 1 and contract_dt.weekday() == 6:
            entry["status"] = "aligned"
            entry["reason"] = "Contract completion is Sunday (weekend); in a 5-day workweek this day does not count—programme correctly completes on next working day."
        elif variance_days == 2 and contract_dt.weekday() == 5:
            entry["status"] = "aligned"
            entry["reason"] = "Contract completion is Saturday (weekend); in a 5-day workweek weekend days do not count—programme correctly completes on next working day (Monday)."
        return entry

    def _create_possession_alignment_entry(
        self,
        contract_value: Any,
        programme_start_value: str,
        field_name: str,
    ) -> Dict[str, Any]:
        """Semantic access/possession: compliant if programme start >= contractual access date; HARD_BREACH if programme start < access."""
        # Normalise contract value (may be string or list of dates)
        access_date_str = ""
        if isinstance(contract_value, list) and contract_value:
            access_date_str = str(contract_value[0]) if contract_value else ""
        elif contract_value:
            access_date_str = str(contract_value).strip()
        if not access_date_str:
            return {
                "contract": contract_value if contract_value else "",
                "programme": programme_start_value or "",
                "variance_days": None,
                "status": "contract_missing",
                "reason": f"Contract {field_name} is missing",
            }
        if not programme_start_value:
            return {
                "contract": access_date_str,
                "programme": "",
                "variance_days": None,
                "status": "programme_missing",
                "reason": f"Programme start (for access comparison) is missing",
            }
        access_dt = self._parse_date(access_date_str)
        programme_dt = self._parse_date(programme_start_value)
        if not access_dt or not programme_dt:
            return self._create_alignment_entry(access_date_str, programme_start_value, field_name)
        variance_days = (programme_dt - access_dt).days
        if variance_days >= 0:
            status = "aligned"
            reason = "Programme start is on or after contractual access date (compliant)."
        else:
            status = "programme_earlier"
            reason = "Programme start is before contractual access date (HARD_BREACH: access not yet due)."
        return {
            "contract": access_date_str,
            "programme": programme_start_value,
            "variance_days": variance_days,
            "status": status,
            "reason": reason,
        }

    def _compare_dates(
        self,
        contract_date: str,
        programme_date: str,
        contract_label: str,
        programme_label: str
    ) -> Dict[str, Any]:
        """Compare two dates and return alignment status (legacy method for backward compatibility)."""
        alignment = self._create_alignment_entry(contract_date, programme_date, contract_label)
        # Convert to old format
        return {
            "status": alignment["status"],
            "contract_date": alignment["contract"],
            "programme_date": alignment["programme"],
            "message": alignment["reason"]
        }
    
    def _compare_completion_dates(
        self,
        contract_completion: str,
        programme_finish: str
    ) -> Dict[str, Any]:
        """Compare completion dates with before/after logic."""
        if not contract_completion:
            return {
                "status": "missing",
                "contract_date": contract_completion,
                "programme_finish": programme_finish,
                "message": "Contract completion date is missing"
            }
        
        if not programme_finish:
            return {
                "status": "missing",
                "contract_date": contract_completion,
                "programme_finish": programme_finish,
                "message": "Programme finish date is missing"
            }
        
        try:
            contract_dt = self._parse_date(contract_completion)
            programme_dt = self._parse_date(programme_finish)
            
            if contract_dt and programme_dt:
                if programme_dt <= contract_dt:
                    return {
                        "status": "before",
                        "contract_date": contract_completion,
                        "programme_finish": programme_finish,
                        "message": "Programme finishes before or on contract completion date"
                    }
                else:
                    return {
                        "status": "after",
                        "contract_date": contract_completion,
                        "programme_finish": programme_finish,
                        "message": "Programme finishes after contract completion date - RISK"
                    }
        except Exception:
            pass
        
        return {
            "status": "unknown",
            "contract_date": contract_completion,
            "programme_finish": programme_finish,
            "message": "Could not compare dates"
        }
    
    def _check_key_dates(
        self,
        contract_data: Dict[str, Any],
        programme_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check if programme contains matching key dates."""
        # Extract key dates from contract (if present in metadata or clauses)
        key_dates = contract_data.get("key_dates", [])
        milestones = programme_summary.get("list_of_milestones", programme_summary.get("key_milestones", []))
        
        return {
            "status": "pass" if milestones else "warning",
            "contract_key_dates_count": len(key_dates),
            "programme_milestones_count": len(milestones),
            "message": f"Programme has {len(milestones)} milestones"
        }
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime object. Handles '28 March 2023', '31 March 2024', ISO, etc."""
        if not date_str or not str(date_str).strip():
            return None
        s = str(date_str).strip()
        formats = [
            '%Y-%m-%d',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%d/%m/%Y',
            '%m/%d/%Y',
            '%Y%m%d',
            '%d %B %Y',   # 28 March 2023
            '%d %b %Y',   # 28 Mar 2023
            '%B %d %Y',   # March 28 2023
            '%b %d %Y',   # Mar 28 2023
        ]
        for fmt in formats:
            try:
                if fmt in ('%d %B %Y', '%d %b %Y', '%B %d %Y', '%b %d %Y'):
                    return datetime.strptime(s, fmt)
                return datetime.strptime(s[:10] if len(s) >= 10 else s, fmt)
            except (ValueError, IndexError, TypeError):
                continue
        return None
    
    def _assess_risks(
        self,
        contract_data: Dict[str, Any],
        p6_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform comprehensive risk assessment."""
        programme_summary = self._extract_programme_data(p6_data)
        alignment = self._perform_nec_alignment_with_summary(contract_data, p6_data, programme_summary)
        return self._assess_risks_with_summaries(contract_data, p6_data, programme_summary, alignment)
    
    def _assess_risks_with_summaries(
        self,
        contract_data: Dict[str, Any],
        p6_data: Dict[str, Any],
        programme_summary: Dict[str, Any],
        alignment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform comprehensive risk assessment with pre-extracted summaries."""
        risks = {
            "critical": [],
            "major": [],
            "minor": []
        }
        
        # Get logic checks
        logic_checks = self.logic_checker.check_logic(p6_data)
        
        # Critical risks – items that prevent acceptance if unresolved
        completion_check = alignment.get("completion_date", {})
        if completion_check.get("outcome") == HARD_BREACH or (
            completion_check.get("status") in ("after", "programme_later") and completion_check.get("outcome") != COMPLIANT
        ):
            risks["critical"].append({
                "area": "Completion date",
                "summary": "The current programme finishes after the contractual completion date.",
                "next_step": "Adjust the programme or agree a revised completion date so the contract date is protected.",
                "source_clause": completion_check.get("source_clause", "Clause 31 / Completion Date"),
                "severity": "High",
            })
        
        possession_check = alignment.get("possession_dates", {})
        if possession_check.get("outcome") == HARD_BREACH:
            risks["critical"].append({
                "area": "Access / possession",
                "summary": "The programme starts work before contractual access is granted.",
                "next_step": "Re-sequence early activities or confirm accelerated access so the contract position is protected.",
                "source_clause": possession_check.get("source_clause", "Clause 31 / Access"),
                "severity": "High",
            })
        
        start_check = alignment.get("starting_date", {})
        if start_check.get("status") in ["contract_missing", "programme_missing"] and start_check.get("outcome") != COMPLIANT:
            risks["critical"].append({
                "area": "Starting date",
                "summary": "Either the contract start date or the programme start date is missing, so the baseline cannot be verified.",
                "next_step": "Populate the starting date in both the contract record and the programme.",
                "source_clause": start_check.get("source_clause", "Clause 31 / Starting Date"),
                "severity": "High",
            })
        
        # Material risks – do not block acceptance but need follow-up
        if logic_checks.get("negative_float", {}).get("count", 0) > 0:
            risks["major"].append({
                "area": "Negative float",
                "summary": f"The programme shows {logic_checks['negative_float']['count']} activities with negative float, indicating the schedule is running late.",
                "next_step": "Review the critical path and resource plan to recover float.",
                "severity": "Moderate",
            })
        
        possession_check = alignment.get("possession_dates", {})
        if possession_check.get("status") in ("contract_missing", "programme_missing") and possession_check.get("outcome") != HARD_BREACH:
            risks["major"].append({
                "area": "Access / possession",
                "summary": "Possession dates are unclear between the contract and programme.",
                "next_step": "Verify access dates and update the programme so mobilisation is clearly sequenced.",
                "severity": "Moderate",
            })
        
        if programme_summary.get("out_of_sequence_activities", []):
            risks["major"].append({
                "area": "Programme logic",
                "summary": f"{len(programme_summary['out_of_sequence_activities'])} activities start before their predecessors finish.",
                "next_step": "Review logic links for those activities so the plan reflects achievable sequencing.",
                "severity": "Moderate",
            })
        
        # Advisory notes – do not indicate non-compliance
        float_dist = programme_summary.get("total_float_distribution", {})
        if float_dist.get("high_positive", 0) > len(programme_summary.get("activities", [])) * 0.3:
            risks["minor"].append({
                "area": "Float profile",
                "summary": "A large proportion of activities have high float, which may suggest durations or logic could tighten further.",
                "next_step": "Review durations and logic so float levels reflect genuine flexibility.",
                "severity": "Advisory",
            })
        
        return risks
    
    def _calculate_validation_summary(
        self,
        validation_output: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Multi-dimension scoring: contract_compliance, programme_completeness,
        programme_realism, governance_and_risk. TIER_1 dominates; TIER_2 influences; TIER_3 zero impact.
        Overall = weighted combination. Fail only for NEC-meaningful reasons (HARD_BREACH).
        """
        alignment = validation_output.get("nec_alignment", {})
        risks = validation_output.get("risks", {})
        programme_summary = validation_output.get("programme_summary", {})
        logic_checks = validation_output.get("logic_checks", {})

        # Collect outcomes from alignment (only TIER_1 and TIER_2 affect scores; TIER_3 excluded)
        tier1_outcomes: List[str] = []
        tier2_outcomes: List[str] = []
        for key in ("starting_date", "completion_date", "possession_dates"):
            entry = alignment.get(key)
            if isinstance(entry, dict) and entry.get("importance_tier") == TIER_1_CRITICAL:
                tier1_outcomes.append(entry.get("outcome", ""))
        scope_coverage = alignment.get("scope_coverage", {})
        obligation_entities_used = isinstance(scope_coverage, dict) and scope_coverage.get("obligation_entities_used")
        pcm = alignment.get("programme_compliance_model") or {}
        # PCM and programme completeness / expected-now/later are INFORMATIONAL ONLY when obligation model is used.
        if isinstance(pcm, dict) and not (isinstance(scope_coverage, dict) and (scope_coverage.get("frozen_used") or obligation_entities_used)):
            overall = pcm.get("overall_status", "unknown")
            tier1_outcomes.append(COMPLIANT if overall == "pass" else (SOFT_BREACH if overall == "partial" else HARD_BREACH))
        if isinstance(scope_coverage, dict) and not obligation_entities_used:
            if scope_coverage.get("importance_tier") == TIER_1_CRITICAL:
                tier1_outcomes.append(scope_coverage.get("outcome", ""))
            if scope_coverage.get("status") == "fail" or scope_coverage.get("scope_items_missing", 0) > 0:
                if HARD_BREACH not in tier1_outcomes:
                    tier1_outcomes.append(HARD_BREACH)
        # When obligation_entities_used: tier1 for scope_coverage is NOT added here; acceptability comes only from oracle below.
        for key in ("key_dates", "delay_damages_alignment"):
            entry = alignment.get(key)
            if isinstance(entry, dict) and entry.get("importance_tier") == TIER_2_SIGNIFICANT:
                tier2_outcomes.append(entry.get("outcome", ""))

        # 1. contract_compliance_score (TIER_1: dates, access, completion, gates)
        tier1_compliant = sum(1 for o in tier1_outcomes if o == COMPLIANT)
        tier1_total = len(tier1_outcomes) if tier1_outcomes else 1
        contract_compliance_score = int((tier1_compliant / tier1_total) * 100) if tier1_total > 0 else 100

        # 2. programme_completeness_score (informational only when obligation_entities_used; does not drive acceptability)
        pcm = alignment.get("programme_compliance_model") or {}
        scope_cov = alignment.get("scope_coverage", {})
        scope_cov_status = scope_cov.get("status", "pass") if isinstance(scope_cov, dict) else "pass"
        frozen_used = isinstance(scope_cov, dict) and scope_cov.get("frozen_used")
        obligation_driven = isinstance(scope_cov, dict) and scope_cov.get("obligation_entities_used")
        req_status = (scope_cov_status if (frozen_used or obligation_driven) else pcm.get("required_activities", {}).get("status", "pass")) if isinstance(pcm, dict) else scope_cov_status
        gates_status = pcm.get("completion_and_takeover_gates", {}).get("status", "pass") if isinstance(pcm, dict) else "pass"
        key_dates_entry = alignment.get("key_dates", {})
        key_ok = key_dates_entry.get("status") == "pass" if isinstance(key_dates_entry, dict) else True
        completeness_parts = [
            100 if req_status == "pass" else (50 if req_status == "partial" else 0),
            100 if gates_status == "pass" else (50 if gates_status == "partial" else 0),
            100 if key_ok else 50,
            100 if scope_cov_status == "pass" else 0,
        ]
        programme_completeness_score = int(sum(completeness_parts) / len(completeness_parts)) if completeness_parts else 100

        # 3. programme_realism_score (logic, float, sequencing - TIER_2)
        negative_float = logic_checks.get("negative_float", {}).get("count", 0) if logic_checks else 0
        broken_logic = logic_checks.get("broken_logic", {}).get("count", 0) if logic_checks else 0
        out_of_seq = len(programme_summary.get("out_of_sequence_activities", []))
        logic_errors_count = len(programme_summary.get("logic_errors", []))
        total_activities = max(1, programme_summary.get("total_activities", 1))
        total_issues = negative_float + broken_logic + out_of_seq + logic_errors_count
        issues_per_activity = total_issues / total_activities
        programme_realism_score = max(0, int(100 - (issues_per_activity * 50)))

        # 4. governance_and_risk_score (circular deps, dangling - TIER_2)
        circular_deps = logic_checks.get("circular_dependencies", {}).get("count", 0) if logic_checks else 0
        circular_deps += len(programme_summary.get("circular_dependencies", []))
        governance_issues = circular_deps + logic_errors_count
        governance_and_risk_score = max(0, 100 - (governance_issues * 20)) if governance_issues else 100

        # Weighted overall (TIER_1 dominates)
        w1, w2, w3, w4 = 0.50, 0.25, 0.15, 0.10
        overall_score = int(
            w1 * contract_compliance_score
            + w2 * programme_completeness_score
            + w3 * programme_realism_score
            + w4 * governance_and_risk_score
        )
        overall_score = min(100, max(0, overall_score))

        # -------------------------------------------------------------------------
        # SINGLE ACCEPTABILITY GATE: When obligation_entities_used, there is exactly one source of truth.
        # Programme is ACCEPTABLE if and only if every mandatory obligation has representation_status in
        # { evidenced, acknowledged, explicit_assumption }. Explicitly forbidden from influencing acceptability:
        # programme_compliance_model, required_activities, NEC/alignment/quality scores, assurance_based,
        # confidence, scope alignment narrative, LLM exemptions.
        # -------------------------------------------------------------------------
        scope_cov = alignment.get("scope_coverage", {})
        if isinstance(scope_cov, dict) and scope_cov.get("obligation_entities_used"):
            explicit_failures = scope_cov.get("acceptability_failure_reasons") or []
            hard_breaches = 1 if explicit_failures else 0
            # PCM, required_activities, alignment_score, assurance_based are not used for acceptability here.
        else:
            hard_breaches = sum(1 for o in tier1_outcomes if o == HARD_BREACH)
            if isinstance(scope_cov, dict) and scope_cov.get("frozen_used"):
                req_list = scope_cov.get("requirements") or []
                if any(not (r.get("matched") is True) for r in req_list if isinstance(r, dict)):
                    if HARD_BREACH not in tier1_outcomes:
                        tier1_outcomes.append(HARD_BREACH)
                    hard_breaches = sum(1 for o in tier1_outcomes if o == HARD_BREACH)
        soft_breaches = sum(1 for o in tier1_outcomes + tier2_outcomes if o == SOFT_BREACH)
        interpretive_count = sum(1 for o in tier1_outcomes + tier2_outcomes if o == INTERPRETIVE)
        # Failure reasons: ONLY from single acceptability oracle when obligation_entities_used. No PCM, no secondary lists.
        failure_reasons: List[str] = []
        if isinstance(scope_cov, dict) and scope_cov.get("obligation_entities_used"):
            failure_reasons = list(scope_cov.get("acceptability_failure_reasons") or [])
        else:
            if isinstance(pcm, dict) and not (isinstance(scope_cov, dict) and (scope_cov.get("frozen_used") or scope_cov.get("obligation_entities_used"))):
                req_detail = pcm.get("required_activities", {})
                if isinstance(req_detail, dict) and req_detail.get("status") != "pass" and req_detail.get("failure_reason"):
                    failure_reasons.append(req_detail["failure_reason"])
            if isinstance(scope_cov, dict) and scope_cov.get("status") == "fail" and not scope_cov.get("obligation_entities_used"):
                explicit_reasons = scope_cov.get("acceptability_failure_reasons")
                if explicit_reasons:
                    failure_reasons.extend(explicit_reasons[:20])
                elif scope_cov.get("failure_reason"):
                    failure_reasons.append(scope_cov["failure_reason"])
                else:
                    missing_list = scope_cov.get("missing", [])
                    if missing_list:
                        failure_reasons.append("Missing from programme: " + "; ".join(missing_list[:15]) + (" ..." if len(missing_list) > 15 else ""))

        if hard_breaches == 0:
            acceptability_status = "ACCEPTABLE"
            acceptability_score = 100
            # Fatal guard: if any mandatory is not represented, must not be acceptable.
            if isinstance(scope_cov, dict) and scope_cov.get("obligation_entities_used"):
                not_rep = scope_cov.get("obligations_not_represented_but_mandatory") or []
                if not_rep:
                    raise RuntimeError(
                        "Acceptability contradiction: cannot mark ACCEPTABLE while obligations_not_represented_but_mandatory exist. "
                        "IDs: " + ", ".join(str(r.get("id", "")) for r in not_rep[:20] if isinstance(r, dict))
                    )
            programme_decision_text = "Programme decision: Acceptable at this stage"
            programme_decision_detail = (
                "Every mandatory obligation is either evidenced by the programme (activities or constraints) or has an explicit assumption recorded. The programme may be accepted."
            )
            programme_reassurance = "Any advisory points noted below can be addressed alongside normal delivery."
        else:
            acceptability_status = "NOT ACCEPTABLE"
            acceptability_score = max(0, 100 - (hard_breaches * 34))
            if not failure_reasons:
                failure_reasons.append("One or more mandatory obligations are not evidenced.")
            programme_decision_text = "Programme decision: Not acceptable at this stage"
            programme_decision_detail = (
                "Several mandatory obligations are not represented in the programme. "
                "They require either explicit programme activities or explicit assumptions (covered by later submission / client responsibility / out of scope at this stage)."
            )
            programme_reassurance = "Scope & constraints may be broadly aligned; the items listed below must be addressed for the programme to be acceptable."

        # -------------------------------------------------------------------------
        # Quality / confidence (supportive language only)
        # -------------------------------------------------------------------------
        quality_score = 100
        if soft_breaches > 0:
            quality_score -= min(50, soft_breaches * 15)
        if interpretive_count > 0:
            quality_score -= min(20, interpretive_count * 5)
        quality_score = max(0, min(100, quality_score))
        # Blend with programme realism and governance (quality dimension only)
        quality_score = int((quality_score * 0.6) + (programme_realism_score * 0.2) + (governance_and_risk_score * 0.2))
        quality_score = max(0, min(100, quality_score))

        quality_messages: List[str] = []
        if soft_breaches > 0:
            quality_messages.append("Some contract checks rely on clarifications that should be tidied up.")
        if interpretive_count > 0:
            quality_messages.append("A few items depend on professional judgement and should be recorded.")
        if programme_realism_score < 100 or governance_and_risk_score < 100:
            quality_messages.append("Programme logic and governance notes should be reviewed to maintain confidence.")
        if quality_messages:
            quality_score_explanation = " ".join(quality_messages)
        else:
            quality_score_explanation = "The programme is well prepared with no outstanding advisory items."
        quality_summary = f"Programme confidence: {quality_score}%."

        # Overall status: when obligation_entities_used, ONLY acceptability_failure_reasons decide. No PCM, score, or assurance may override.
        scope_cov_for_status = alignment.get("scope_coverage", {})
        obligation_driven_status = isinstance(scope_cov_for_status, dict) and scope_cov_for_status.get("obligation_entities_used")
        if obligation_driven_status:
            overall_status = "pass" if not failure_reasons else "fail"
            # Tripwire: pass only when no mandatory obligations are not represented.
            if overall_status == "pass" and failure_reasons:
                raise RuntimeError(
                    "Acceptability contradiction: overall_status=pass but acceptability_failure_reasons non-empty. "
                    "Obligation alignment is the single source of truth."
                )
            not_rep = scope_cov_for_status.get("obligations_not_represented_but_mandatory") or []
            if overall_status == "pass" and not_rep:
                raise RuntimeError(
                    "Acceptability contradiction: programme pass but obligations_not_represented_but_mandatory non-empty. "
                    "IDs: " + ", ".join(str(r.get("id", "")) for r in not_rep[:20] if isinstance(r, dict))
                )
        else:
            if acceptability_status == "NOT ACCEPTABLE":
                overall_status = "fail"
            elif soft_breaches > 2 or quality_score < 50:
                overall_status = "needs_attention"
            elif quality_score < 75:
                overall_status = "needs_attention"
            else:
                overall_status = "pass"

        summary_parts = [
            programme_decision_detail,
            f"{quality_summary} {quality_score_explanation}",
        ]
        stage_label = pcm.get("programme_stage_label") or _STAGE_TITLES.get(pcm.get("programme_stage", ""), pcm.get("programme_stage", ""))
        stage_reason = pcm.get("programme_stage_reasoning", "")

        if failure_reasons and acceptability_status != "ACCEPTABLE":
            summary_parts.append("Reason: " + "; ".join(failure_reasons))
        if stage_label:
            summary_parts.append(f"Stage classification: {stage_label}.")
        if stage_reason:
            summary_parts.append(stage_reason)
        summary_explanation = " ".join(part for part in summary_parts if part).strip()

        scope_cov_for_missing = alignment.get("scope_coverage", {})
        # SINGLE SOURCE: When obligation_entities_used, executive summary, required actions, and missing lists
        # MUST come only from acceptability_failure_reasons. No other lists may feed decision or "what must be added".
        obligation_driven_report = isinstance(scope_cov_for_missing, dict) and scope_cov_for_missing.get("obligation_entities_used")
        if obligation_driven_report:
            acceptability_failures_plain = list(failure_reasons)
            acceptability_missing_items = list(failure_reasons)
            acceptability_missing_scope_items = []
            acceptability_missing_constraints = []
        else:
            acceptability_missing_items = scope_cov_for_missing.get("missing", []) if isinstance(scope_cov_for_missing, dict) else []
            acceptability_missing_scope_items = scope_cov_for_missing.get("missing_scope_items", []) if isinstance(scope_cov_for_missing, dict) else []
            acceptability_missing_constraints = scope_cov_for_missing.get("missing_constraints", []) if isinstance(scope_cov_for_missing, dict) else []
            acceptability_failures_plain = scope_cov_for_missing.get("acceptability_failure_reasons", []) if isinstance(scope_cov_for_missing, dict) else []

        # Full obligations report: obligation entities (four types) or frozen list
        frozen_requirements_report: Optional[List[Dict[str, Any]]] = None
        expected_programme_representations_report: Optional[List[Dict[str, Any]]] = None
        expected_representations_note: Optional[str] = None
        programme_obligations_report: Optional[List[Dict[str, Any]]] = None
        scope_evidence_table: Optional[List[Dict[str, Any]]] = None
        constraints_control_report: Optional[List[Dict[str, Any]]] = None
        assurance_items_requiring_confirmation: Optional[List[Dict[str, Any]]] = None
        if isinstance(scope_cov_for_missing, dict) and scope_cov_for_missing.get("obligation_entities_used"):
            programme_obligations_report = scope_cov_for_missing.get("programme_obligations") or []
            scope_evidence_table = scope_cov_for_missing.get("scope_evidence_table") or []
            constraints_control_report = scope_cov_for_missing.get("constraints_control") or []
            frozen_requirements_report = scope_cov_for_missing.get("requirements") or []
            assurance_items_requiring_confirmation = scope_cov_for_missing.get("assurance_items_requiring_confirmation") or []
        elif isinstance(scope_cov_for_missing, dict) and scope_cov_for_missing.get("frozen_used"):
            frozen_requirements_report = scope_cov_for_missing.get("requirements") or []
            expected_programme_representations_report = scope_cov_for_missing.get("expected_programme_representations") or []
            expected_representations_note = scope_cov_for_missing.get("expected_programme_representations_note") or (
                "Expected programme representations (derived from primary obligations; "
                "for explanation only; do not drive acceptability). Each item references parent_obligation_id."
            )

        # Backward compatibility: nec_alignment_score = contract_compliance_score; schedule_quality_score = programme_realism_score
        out: Dict[str, Any] = {
            "acceptability_status": acceptability_status,
            "acceptability_missing_items": acceptability_missing_items,
            "acceptability_failures_plain": acceptability_failures_plain,
            "acceptability_missing_scope_items": acceptability_missing_scope_items,
            "acceptability_missing_constraints": acceptability_missing_constraints,
            "acceptability_score": acceptability_score,
            "quality_score": quality_score,
            "quality_score_explanation": quality_score_explanation,
            "contract_compliance_score": contract_compliance_score,
            "programme_completeness_score": programme_completeness_score,
            "programme_realism_score": programme_realism_score,
            "governance_and_risk_score": governance_and_risk_score,
            "overall_score": overall_score,
            "overall_status": overall_status,
            "nec_alignment_score": contract_compliance_score,
            "schedule_quality_score": programme_realism_score,
            "hard_breaches": hard_breaches,
            "soft_breaches": soft_breaches,
            "issues_found": len(risks.get("critical", [])) + len(risks.get("major", [])) + len(risks.get("minor", [])),
            "critical_issues": len(risks.get("critical", [])),
            "major_issues": len(risks.get("major", [])),
            "minor_issues": len(risks.get("minor", [])),
            "score_weights": {"contract_compliance": w1, "programme_completeness": w2, "programme_realism": w3, "governance_and_risk": w4},
            "summary_explanation": summary_explanation,
            "acceptability_failure_reasons": failure_reasons,
            "programme_stage": pcm.get("programme_stage", ""),
            "programme_stage_label": stage_label,
            "programme_stage_reasoning": stage_reason,
            "contract_type": pcm.get("contract_type", "UNKNOWN"),
            "programme_intent": pcm.get("programme_intent", "mixed"),
            "programme_decision_text": programme_decision_text,
            "programme_decision_detail": programme_decision_detail,
            "programme_reassurance": programme_reassurance,
            "quality_summary": quality_summary,
            "quality_score_explanation": quality_score_explanation,
        }
        if frozen_requirements_report is not None:
            out["frozen_requirements_report"] = frozen_requirements_report
        if expected_programme_representations_report is not None:
            out["expected_programme_representations"] = expected_programme_representations_report
            out["expected_programme_representations_note"] = expected_representations_note
        if programme_obligations_report is not None:
            out["programme_obligations_report"] = programme_obligations_report
            out["what_must_be_added_to_accept"] = acceptability_failures_plain
        if scope_evidence_table is not None:
            out["scope_evidence_table"] = scope_evidence_table
        if constraints_control_report is not None:
            out["constraints_control_report"] = constraints_control_report
        if assurance_items_requiring_confirmation is not None:
            out["assurance_items_requiring_confirmation"] = assurance_items_requiring_confirmation
            out["assurance_items_requiring_confirmation_note"] = (
                "Assurance items requiring professional confirmation (not acceptability failures). "
                "These may be satisfied by governance, standards reference, or professional judgement."
            )
        return out

    def _generate_nec_alignment_detailed(
        self,
        contract_summary: Dict[str, Any],
        programme_summary: Dict[str, Any],
        alignment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate detailed NEC alignment for all clauses."""
        detailed = {}
        
        # Define all NEC clauses to check
        clause_mappings = {
            "3.1": {
                "contract_key": "starting_date",
                "programme_key": "programme_start_date",  # prefer programme start (milestone), fallback data_date
                "programme_key_fallback": "data_date",
                "description": "Starting Date"
            },
            "3.2": {
                "contract_key": None,
                "programme_key": "earliest_activity_start",
                "programme_key_fallback": None,
                "description": "Possession Dates"
            },
            "3.3": {
                "contract_key": "completion_date",
                "programme_key": "programme_finish_date",  # prefer programme finish (Completion/Finish Milestone)
                "programme_key_fallback": "latest_activity_finish",
                "description": "Completion Date"
            },
            "3.5": {
                "contract_key": "submit_first_programme_within",
                "programme_key": None,
                "description": "First Programme Submission"
            },
            "3.6": {
                "contract_key": "revised_programme_interval",
                "programme_key": None,
                "description": "Revised Programme Interval"
            },
            "3.7": {
                "contract_key": "delay_damages",
                "programme_key": None,
                "description": "Delay Damages"
            },
            "4.1": {
                "contract_key": None,
                "programme_key": None,
                "description": "Defects Date"
            },
            "4.2": {
                "contract_key": None,
                "programme_key": None,
                "description": "Defect Correction Period"
            },
            "4.3": {
                "contract_key": None,
                "programme_key": None,
                "description": "Landscaping Maintenance Period"
            },
            "5.2": {
                "contract_key": None,
                "programme_key": None,
                "description": "Assessment Interval"
            },
            "5.3": {
                "contract_key": None,
                "programme_key": None,
                "description": "Payment Period"
            },
            "5.5": {
                "contract_key": "retention_percentage",
                "programme_key": None,
                "description": "Retention Percentage"
            },
            "5.6": {
                "contract_key": None,
                "programme_key": None,
                "description": "Bond Amount"
            },
            "6.1": {
                "contract_key": None,
                "programme_key": None,
                "description": "Weather Recording Location"
            },
            "6.2": {
                "contract_key": None,
                "programme_key": None,
                "description": "Weather Measurement Data"
            },
            "6.3": {
                "contract_key": None,
                "programme_key": None,
                "description": "Historical Weather Records Source"
            }
        }
        
        # Extract clauses from contract_summary
        clauses = contract_summary.get("clauses", {})
        
        for clause_num, mapping in clause_mappings.items():
            # Get contract value
            contract_value = ""
            if mapping["contract_key"]:
                contract_field = contract_summary.get(mapping["contract_key"], {})
                contract_value = contract_field.get("value", "") if isinstance(contract_field, dict) else str(contract_field)
            
            # If not found in direct fields, check clauses
            if not contract_value and clause_num in clauses:
                contract_value = clauses[clause_num].get("value", "")
            
            # Get programme value (with optional fallback)
            programme_value = ""
            if mapping["programme_key"]:
                programme_value = programme_summary.get(mapping["programme_key"], "")
            if not programme_value and mapping.get("programme_key_fallback"):
                programme_value = programme_summary.get(mapping["programme_key_fallback"], "")
            
            # Calculate variance if both dates are present
            variance_days = None
            status = "unknown"
            
            if not contract_value:
                status = "contract_missing"
            elif not programme_value and mapping["programme_key"]:
                status = "programme_missing"
            elif contract_value and programme_value:
                # Try to calculate variance for dates
                contract_dt = self._parse_date(contract_value)
                programme_dt = self._parse_date(programme_value)
                
                if contract_dt and programme_dt:
                    variance_days = (programme_dt - contract_dt).days
                    if variance_days == 0:
                        status = "aligned"
                    else:
                        status = "mismatch"
                elif contract_value == programme_value:
                    status = "aligned"
                else:
                    status = "mismatch"
            else:
                # Non-date fields - just check if present
                if contract_value:
                    status = "present"
                else:
                    status = "contract_missing"
            
            detailed[clause_num] = {
                "contract_value": contract_value if contract_value else "",
                "programme_value": programme_value if programme_value else "",
                "variance_days": variance_days,
                "status": status,
                "description": mapping["description"],
                "source_clause": f"Clause {clause_num}" if "." in str(clause_num) else mapping["description"],
                "source_type": "explicit" if contract_value else "inferred",
                "validation_basis": "date" if (mapping.get("programme_key") and "date" in (mapping.get("programme_key") or "").lower()) else "existence",
            }
        
        return detailed
    
    def _calculate_programme_kpis(
        self,
        programme_summary: Dict[str, Any],
        p6_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate programme key performance indicators."""
        activities = programme_summary.get("activities", [])
        total_activities = len(activities)
        
        # Calculate critical path length
        critical_path = programme_summary.get("critical_path", [])
        critical_path_length_days = 0
        if critical_path:
            # Find earliest start and latest finish in critical path
            earliest_start = None
            latest_finish = None
            for act in critical_path:
                start = act.get("start")
                finish = act.get("finish")
                if start:
                    start_dt = self._parse_date(start)
                    if start_dt and (not earliest_start or start_dt < earliest_start):
                        earliest_start = start_dt
                if finish:
                    finish_dt = self._parse_date(finish)
                    if finish_dt and (not latest_finish or finish_dt > latest_finish):
                        latest_finish = finish_dt
            
            if earliest_start and latest_finish:
                critical_path_length_days = (latest_finish - earliest_start).days
        
        # Calculate percentage with no predecessor
        logic = p6_data.get("logic", [])
        activity_ids = {a.get("task_id") or a.get("id", "") for a in activities}
        activities_with_predecessors = set()
        for rel in logic:
            succ_id = rel.get("succ_task_id") or rel.get("successor_id", "")
            if succ_id in activity_ids:
                activities_with_predecessors.add(succ_id)
        
        percentage_no_predecessor = ((total_activities - len(activities_with_predecessors)) / total_activities * 100) if total_activities > 0 else 0.0
        
        # Calculate percentage with no successor
        activities_with_successors = set()
        for rel in logic:
            pred_id = rel.get("pred_task_id") or rel.get("predecessor_id", "")
            if pred_id in activity_ids:
                activities_with_successors.add(pred_id)
        
        percentage_no_successor = ((total_activities - len(activities_with_successors)) / total_activities * 100) if total_activities > 0 else 0.0
        
        # Calculate percentage with hard constraints
        constraints = programme_summary.get("constraints", [])
        # Count activities with hard constraints (simplified - assume all constraints are hard)
        percentage_hard_constraints = (len(constraints) / total_activities * 100) if total_activities > 0 else 0.0
        
        # Calculate max negative float
        negative_float_list = programme_summary.get("negative_float_list", [])
        max_negative_float = 0.0
        if negative_float_list:
            max_negative_float = min([act.get("float", 0) for act in negative_float_list])
        
        # Calculate average float
        float_values = [a.get("float", 0) for a in activities]
        average_float = sum(float_values) / len(float_values) if float_values else 0.0
        
        return {
            "total_activities": total_activities,
            "critical_path_length_days": critical_path_length_days,
            "percentage_no_predecessor": round(percentage_no_predecessor, 2),
            "percentage_no_successor": round(percentage_no_successor, 2),
            "percentage_hard_constraints": round(percentage_hard_constraints, 2),
            "max_negative_float": round(max_negative_float, 2),
            "average_float": round(average_float, 2)
        }
    
    def _generate_recommendations(
        self,
        risks: Dict[str, Any],
        alignment: Dict[str, Any],
        programme_summary: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate structured recommendations based on validation findings."""
        recommendations = []
        
        # Generate recommendations from risks
        for risk_level in ["critical", "major", "minor"]:
            for risk in risks.get(risk_level, []):
                recommendations.append({
                    "issue": risk.get("description", ""),
                    "impact": risk.get("impact", ""),
                    "recommendation": risk.get("recommendation", "")
                })
        
        # Generate recommendations from alignment issues
        starting_date = alignment.get("starting_date", {})
        if starting_date.get("status") in ["contract_missing", "programme_missing", "mismatch"]:
            recommendations.append({
                "issue": f"Starting date alignment issue: {starting_date.get('reason', '')}",
                "impact": "High - programme start date must match contract starting date",
                "recommendation": "Ensure contract Starting Date (3.1) is populated and programme data date matches"
            })
        
        completion_date = alignment.get("completion_date", {})
        if completion_date.get("status") == "after":
            recommendations.append({
                "issue": "Programme completion date is after contract completion date",
                "impact": "Critical - potential delay damages and contract breach",
                "recommendation": "Review programme logic, resource allocation, and activity durations to bring completion forward"
            })
        
        # Generate recommendations from programme KPIs
        negative_float_list = programme_summary.get("negative_float_list", [])
        if negative_float_list:
            recommendations.append({
                "issue": f"Programme has {len(negative_float_list)} activities with negative float",
                "impact": "Major - schedule is behind and may not be achievable",
                "recommendation": "Review critical path activities, reduce durations where possible, or adjust contract completion date"
            })
        
        out_of_sequence = programme_summary.get("out_of_sequence_activities", [])
        if out_of_sequence:
            recommendations.append({
                "issue": f"Programme has {len(out_of_sequence)} out-of-sequence activities",
                "impact": "Medium - schedule logic may be incorrect",
                "recommendation": "Review activity sequencing and update logic relationships"
            })
        
        logic_errors = programme_summary.get("logic_errors", [])
        if logic_errors:
            recommendations.append({
                "issue": f"Programme has {len(logic_errors)} logic errors (broken relationships)",
                "impact": "Major - schedule integrity compromised",
                "recommendation": "Fix broken logic relationships and ensure all predecessor/successor links are valid"
            })
        
        return recommendations
    
    def _calculate_schedule_health(
        self,
        programme_summary: Dict[str, Any],
        logic_checks: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate schedule health metrics. Always returns all fields even if data is missing."""
        total_activities = programme_summary.get("total_activities", 0)
        negative_float_count = len(programme_summary.get("negative_float_list", []))
        out_of_sequence_count = len(programme_summary.get("out_of_sequence_activities", []))
        logic_errors_count = len(programme_summary.get("logic_errors", []))
        circular_deps_count = len(programme_summary.get("circular_dependencies", []))
        
        # Add logic check counts if available
        if logic_checks:
            negative_float_count = max(negative_float_count, logic_checks.get("negative_float", {}).get("count", 0))
            circular_deps_count = max(circular_deps_count, logic_checks.get("circular_dependencies", {}).get("count", 0))
        
        # Calculate health score (0-100)
        total_issues = negative_float_count + out_of_sequence_count + logic_errors_count + circular_deps_count
        health_score = max(0, 100 - (total_issues * 10)) if total_activities > 0 else 100
        
        return {
            "total_activities": total_activities,
            "negative_float_count": negative_float_count,
            "out_of_sequence_count": out_of_sequence_count,
            "logic_errors_count": logic_errors_count,
            "circular_dependencies_count": circular_deps_count,
            "health_score": health_score,
            "status": "healthy" if health_score >= 80 else "needs_attention" if health_score >= 50 else "critical"
        }