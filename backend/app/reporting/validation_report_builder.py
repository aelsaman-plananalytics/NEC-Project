"""
Validation Report Builder.

Builds the mandatory Programme Validation Report structure (Sections A–G)
from validation JSON. Presentation only—no recalculation, no omission of findings.

Type-safe: handles validation output where fields may be dict, list, or string.
"""

import re
from collections import Counter, defaultdict
from typing import Dict, Any, List, Optional
from datetime import datetime

EXPECTED_NOW = "EXPECTED_NOW"


def _safe_get(obj: Any, key: str, default: Any = None) -> Any:
    """Safe .get(): return default if obj is not a dict."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default


def _safe_dict(obj: Any) -> dict:
    """Return obj if dict, else empty dict."""
    return obj if isinstance(obj, dict) else {}


def _safe_list(obj: Any) -> list:
    """Return obj if list, else empty list."""
    return obj if isinstance(obj, list) else []


def _safe_str(obj: Any, default: str = "") -> str:
    """Return obj as string if not None, else default."""
    if obj is None:
        return default
    return str(obj).strip() or default
EXPECTED_LATER = "EXPECTED_LATER"
EXPECTATION_LABELS = {
    EXPECTED_NOW: "Required at this stage",
    EXPECTED_LATER: "Required later in the contract",
}


def _extract_text_list(items: Any) -> List[str]:
    texts: List[str] = []
    for item in (_safe_list(items) if items is not None else []):
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(
                _safe_get(item, "text")
                or _safe_get(item, "value")
                or _safe_get(item, "description")
                or _safe_get(item, "name")
                or ""
            ).strip()
        else:
            text = ""
        if text:
            texts.append(text)
    return texts


def _tokenise(text: str) -> set:
    if not text:
        return set()
    return set(re.findall(r"[A-Za-z]{2,}", text.lower()))


def _canonical_text(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


# Scope classification (reporting only): items are classified to report representation appropriately.
SCOPE_ACTIVITY_DELIVERABLE = "ACTIVITY_DELIVERABLE"
SCOPE_ASSURANCE_QUALITY = "ASSURANCE_QUALITY"
SCOPE_GOVERNANCE_APPROVAL = "GOVERNANCE_APPROVAL"

# Coverage strength levels (reporting refinement only; does not change matching).
COVERAGE_EXPLICIT = "Explicitly represented"
COVERAGE_IMPLICIT = "Implicitly represented"
COVERAGE_ASSURANCE = "Assurance-based coverage"
COVERAGE_NONE = "Not represented"

# Confidence bands (descriptive only; do not affect acceptability or scores).
CONFIDENCE_HIGH = "High confidence"
CONFIDENCE_MODERATE = "Moderate confidence"
CONFIDENCE_JUDGEMENT_REQUIRED = "Judgement required"

# Activity load transparency: threshold above which we add an informational note (obligations per activity).
ACTIVITY_LOAD_THRESHOLD = 4

_ASSURANCE_KEYWORDS = {
    "standard", "quality", "performance", "outcome", "principle", "compliance",
    "specification", "environmental protection", "safety", "assurance", "controls",
}
_GOVERNANCE_KEYWORDS = {
    "review", "approval", "accept", "stakeholder", "inspection", "gate", "milestone",
    "sign-off", "sign off", "verification", "validation", "approve", "consultation",
}


def _classify_scope_item(scope_text: str) -> str:
    """Classify scope item for reporting: ACTIVITY_DELIVERABLE, ASSURANCE_QUALITY, or GOVERNANCE_APPROVAL."""
    if not scope_text:
        return SCOPE_ACTIVITY_DELIVERABLE
    tokens = _tokenise(scope_text)
    # Governance first (reviews, approvals, gates) – more specific
    if tokens & _GOVERNANCE_KEYWORDS:
        return SCOPE_GOVERNANCE_APPROVAL
    # Assurance/quality – standards, outcomes, principles
    if tokens & _ASSURANCE_KEYWORDS:
        return SCOPE_ASSURANCE_QUALITY
    return SCOPE_ACTIVITY_DELIVERABLE


def _find_governance_evidence(scope_text: str, programme_activities: List[str]) -> List[str]:
    """Find programme activities that may represent governance/approval scope (milestones, reviews, gates)."""
    evidence: List[str] = []
    governance_activity_tokens = {"gate", "gateway", "review", "approval", "approve", "inspection", "sign", "milestone", "consultation", "acceptance", "verification", "validation"}
    for act in programme_activities:
        if not act:
            continue
        act_tokens = _tokenise(act)
        if act_tokens & governance_activity_tokens:
            evidence.append(act)
    return sorted(set(evidence))[:5]


def build_validation_report(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build the mandatory report structure from validation JSON.
    Does not change validation results or recalculate scores.
    Never recomputes or infers acceptability; mirrors validator output only.
    Do not say 'acceptable' unless validator explicitly says so; any contradiction raises and no report is generated.
    Type-safe: handles dict, list, or string values in validation output.
    """
    data = _safe_dict(data)
    validation_summary = _safe_dict(_safe_get(data, "validation_summary"))
    alignment = _safe_dict(_safe_get(data, "alignment"))
    contract_summary = _safe_dict(_safe_get(data, "contract_summary"))
    programme_summary = _safe_dict(_safe_get(data, "programme_summary"))
    risks = _safe_dict(_safe_get(data, "risks") or _safe_get(data, "risk_summary"))
    pcm = _safe_dict(_safe_get(alignment, "programme_compliance_model"))
    metadata = _safe_dict(_safe_get(data, "metadata"))
    nec_detailed = _safe_dict(_safe_get(data, "nec_alignment_detailed"))

    scope_coverage = _safe_dict(_safe_get(alignment, "scope_coverage"))
    # Report contradiction tripwire: do not render pass if any mandatory obligation is unaligned or has only covered_by_later_submission.
    if _safe_get(validation_summary, "overall_status") == "pass":
        obligations_report = _safe_list(_safe_get(scope_coverage, "obligations_report"))
        if _safe_get(scope_coverage, "obligation_entities_used"):
            failing = [
                o.get("id") for o in obligations_report
                if o.get("mandatory_for_acceptance") and not o.get("aligned")
            ]
            if failing:
                raise RuntimeError(
                    "REPORT CONTRADICTION: pass with unaligned obligations {}".format(failing)
                )
            covered_later = [
                o.get("id") for o in obligations_report
                if o.get("mandatory_for_acceptance") and (_safe_str(o.get("explicit_assumption")).strip().lower() == "covered_by_later_submission")
            ]
            if covered_later:
                raise RuntimeError(
                    "REPORT CONTRADICTION: pass while mandatory obligation(s) have only 'covered_by_later_submission' (must not justify acceptance): {}".format(covered_later)
                )
    scope_sec = _section_scope_contract_alignment(contract_summary, pcm, programme_summary, validation_summary, scope_coverage)
    section_d = _section_d(pcm, alignment)
    section_b = _section_b(alignment, validation_summary)
    programme_stage_context = _programme_stage_context(pcm)
    section_a = _section_a(validation_summary, metadata, programme_stage_context)
    user_confirmations_section = _section_user_confirmations(_safe_list(_safe_get(data, "user_confirmations")))

    return {
        "section_a_executive_summary": section_a,
        "section_b_what_determined_outcome": section_b,
        "section_scope_contract_alignment": scope_sec,
        "section_c_dates": _section_c(alignment, contract_summary, programme_summary),
        "section_d_required_activities_and_gates": section_d,
        "section_e_quality_realism_advisory": _section_e(programme_summary, validation_summary, risks),
        "section_f_excluded_from_scoring": _section_f(alignment),
        "section_g_traceability_appendix": _section_g(alignment, nec_detailed),
        "section_h_next_steps": _section_h_next_steps(pcm, validation_summary, risks),
        "section_what_to_review_next": _section_what_to_review_next(scope_sec, section_d, validation_summary),
        "section_user_confirmations_and_notes": user_confirmations_section,
        "metadata": {
            "report_title": "Programme Validation Report",
            "contract_file": _safe_str(_safe_get(metadata, "contract_file"), "—"),
            "xer_file": _safe_str(_safe_get(metadata, "xer_file"), "—"),
            "validation_timestamp": _safe_str(_safe_get(metadata, "validation_timestamp")),
            "programme_stage_context": programme_stage_context,
        },
    }


def _programme_stage_context(pcm: Dict[str, Any]) -> str:
    """Infer programme maturity for explanatory context only. Does not change rules or acceptability."""
    p = _safe_dict(pcm)
    label = (_safe_get(p, "programme_stage_label") or _safe_get(p, "programme_stage") or "").strip().lower()
    if not label:
        return ""
    if "early" in label or "outline" in label or "preliminary" in label:
        stage = "early-stage / outline"
    elif "design" in label:
        stage = "design-stage"
    elif "construction" in label or "build" in label:
        stage = "construction-stage"
    else:
        stage = label.replace("_", " ").strip() or ""
    if not stage:
        return ""
    return f"Findings are interpreted in the context of a {stage} programme."


def _section_what_to_review_next(
    scope_sec: Dict[str, Any],
    section_d: Dict[str, Any],
    validation_summary: Dict[str, Any],
) -> Dict[str, Any]:
    """Guidance on what to review next. High-signal only; calm, professional language. Does not list everything."""
    items: List[str] = []
    scope_rows = _safe_list(scope_sec.get("scope_rows"))
    activity_load_notes = _safe_list(scope_sec.get("activity_load_notes"))
    required_table = _safe_list(section_d.get("required_activities_table"))
    acceptability = _safe_str(_safe_get(validation_summary, "acceptability_status"))

    # Activities supporting multiple obligations
    if activity_load_notes:
        items.append("One or more programme activities support several contract requirements; consider adding more detail as the programme matures.")

    # Assurance-based items: surfaced only as "Requires governance / future submission". Never imply they affect acceptability.
    assurance_count = sum(1 for r in scope_rows if _safe_dict(r).get("representation_status") == COVERAGE_ASSURANCE)
    if assurance_count:
        items.append("Some scope items require governance or future submission; ensure they are covered in your project management arrangements.")

    # Implicit coverage areas
    implicit_scope = sum(1 for r in scope_rows if _safe_dict(r).get("representation_status") == COVERAGE_IMPLICIT)
    if implicit_scope:
        items.append("Some scope items have implicit programme coverage; you may wish to add more explicit activities as the programme develops.")

    # Judgement-required required activities (missing or unclear)
    judgement_required = sum(1 for r in required_table if _safe_dict(r).get("confidence_band") == CONFIDENCE_JUDGEMENT_REQUIRED)
    if judgement_required and acceptability != "ACCEPTABLE":
        items.append("Required activities that are not yet shown should be added so the programme can be accepted at this stage.")

    if not items:
        items.append("No specific review priorities identified; use the sections above to focus your next steps.")

    return {
        "section_intro": "The following may help focus your next review. This is guidance only.",
        "items": items[:5],
    }


def _section_user_confirmations(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """User confirmations and notes for the report. Clearly separated from system assessment."""
    items: List[Dict[str, Any]] = []
    for e in entries:
        ent = _safe_dict(e) if isinstance(e, dict) else {}
        note = _safe_str(_safe_get(ent, "note") or _safe_get(ent, "note_text"))
        if not note:
            continue
        ts = _safe_str(_safe_get(ent, "timestamp"))
        finding_id = _safe_str(_safe_get(ent, "finding_id") or _safe_get(ent, "findingId"), "—")
        items.append({
            "finding_id": finding_id,
            "note": note,
            "timestamp": ts,
            "confirmed": _safe_get(ent, "confirmed") is not False,
        })
    return {
        "section_intro": "The following confirmations and notes were added by the user. They are not part of the system assessment and represent professional judgement.",
        "items": items,
    }


def _section_h_next_steps(pcm: Dict[str, Any], validation_summary: Dict[str, Any], risks: Dict[str, Any]) -> Dict[str, Any]:
    """Concrete next steps for the delivery team."""
    actions: List[str] = []
    required = _safe_dict(_safe_get(pcm, "required_activities"))
    entries = _safe_list(_safe_get(required, "entries"))
    for entry in entries:
        entry = _safe_dict(entry) if not isinstance(entry, dict) else entry
        if _safe_get(entry, "expectation") == EXPECTED_NOW and _safe_get(entry, "status") == "NOT_FOUND":
            requirement = _safe_str(_safe_get(entry, "requirement"), "Unnamed activity")
            actions.append(f"Add programme detail for “{requirement}” so it is visible at this stage of the contract.")
    for severity in ("critical", "major"):
        for item in _safe_list(_safe_get(risks, severity)):
            item = _safe_dict(item) if not isinstance(item, dict) else item
            step = _safe_get(item, "next_step")
            if step:
                actions.append(str(step))
    if not actions:
        if _safe_get(validation_summary, "acceptability_status") == "ACCEPTABLE":
            actions.append("No immediate compliance actions are required. Continue to monitor the advisory observations listed above.")
        else:
            actions.append("Address the highlighted items so the programme can move to an acceptable position.")
    return {"next_steps": actions}


def _section_a(
    validation_summary: Dict[str, Any],
    metadata: Dict[str, Any],
    programme_stage_context: str = "",
) -> Dict[str, Any]:
    """Section A — Executive summary written for the Project Manager."""
    vs = _safe_dict(validation_summary)
    decision_heading = _safe_str(_safe_get(vs, "programme_decision_text"), "Programme decision")
    decision_detail = _safe_str(_safe_get(vs, "programme_decision_detail"))
    reassurance = _safe_str(_safe_get(vs, "programme_reassurance"))
    q_score = _safe_get(vs, "quality_score") or 0
    quality_summary = _safe_str(_safe_get(vs, "quality_summary"), f"Programme confidence: {q_score}%.")
    quality_detail = _safe_str(_safe_get(vs, "quality_score_explanation"))
    failure_reasons = _safe_list(_safe_get(vs, "acceptability_failure_reasons"))
    headline_reason = failure_reasons[0] if failure_reasons else ""

    executive_summary = [
        decision_heading,
        decision_detail,
    ]
    if programme_stage_context:
        executive_summary.append(programme_stage_context)
    if headline_reason and _safe_get(vs, "acceptability_status") != "ACCEPTABLE":
        executive_summary.append(f"Main reason: {headline_reason}")
    executive_summary.append(quality_summary)
    if quality_detail:
        executive_summary.append(quality_detail)
    if reassurance:
        executive_summary.append(reassurance)

    return {
        "decision_heading": decision_heading,
        "decision_detail": decision_detail,
        "headline_reason": headline_reason,
        "quality_summary": quality_summary,
        "quality_detail": quality_detail,
        "reassurance": reassurance,
        "programme_stage_context": programme_stage_context,
        "executive_summary_text": " ".join(part for part in executive_summary if part),
    }


def _section_b(alignment: Dict[str, Any], validation_summary: Dict[str, Any]) -> Dict[str, Any]:
    """Section B — Plain-English explanation of what drove the decision."""
    attention_items: List[Dict[str, str]] = []
    reassurance_items: List[Dict[str, str]] = []
    align = _safe_dict(alignment)

    alignment_keys = [
        ("starting_date", "Starting date"),
        ("completion_date", "Completion date"),
        ("possession_dates", "Access / possession"),
        ("key_dates", "Key dates"),
        ("programme_submission", "Programme submission cycle"),
        ("delay_damages_alignment", "Delay damages alignment"),
        ("weather_alignment", "Weather data arrangements"),
    ]

    def _clean(text: str) -> str:
        if not text:
            return ""
        for word in ["HARD_BREACH", "SOFT_BREACH", "INTERPRETIVE", "Tier", "tier"]:
            text = text.replace(word, "").strip()
        return text

    has_interpretive = False
    for key, label in alignment_keys:
        entry = _safe_dict(_safe_get(align, key))
        if not entry:
            continue
        status = _safe_str(_safe_get(entry, "status"))
        reason = _clean(_safe_str(_safe_get(entry, "reason")))
        contract = _safe_str(_safe_get(entry, "contract"), "—")
        programme = _safe_str(_safe_get(entry, "programme"), "—")
        outcome = _safe_str(_safe_get(entry, "outcome"))
        message = reason or f"{label} has been checked."
        if outcome in ("SOFT_BREACH", "INTERPRETIVE") or "working" in reason.lower() or "weekend" in reason.lower():
            has_interpretive = True

        needs_action = outcome == "HARD_BREACH" or status in ("programme_later", "programme_earlier", "programme_missing", "contract_missing", "fail", "mismatch")
        if needs_action:
            attention_items.append({
                "requirement": label,
                "observation": message or f"{label} needs attention.",
                "action": "Update the programme or contract entry so this item can be signed off.",
                "contract": contract,
                "programme": programme,
            })
        else:
            reassurance_items.append({
                "requirement": label,
                "message": message or f"{label} aligns with the contract.",
                "contract": contract,
                "programme": programme,
            })

    alternative_interpretation = ""
    if has_interpretive and attention_items:
        alternative_interpretation = (
            "An alternative interpretation could be that some variance is due to working-day or calendar convention; "
            "the assessment above reflects the interpretation used for this report."
        )

    intro = "Critical comparisons between the contract and the programme are summarised below."
    return {
        "section_intro": intro,
        "items_requiring_attention": attention_items,
        "items_in_good_order": reassurance_items,
        "alternative_interpretation": alternative_interpretation,
    }


def _section_scope_contract_alignment(
    contract_summary: Dict[str, Any],
    pcm: Dict[str, Any],
    programme_summary: Dict[str, Any],
    validation_summary: Dict[str, Any],
    scope_coverage: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """How the programme reflects contract scope and constraints using actual evidence.
    Presentation only: acceptability and failure reasons come from validation_summary; we do not re-derive or soften."""
    scope_coverage = scope_coverage or {}
    cs = _safe_dict(contract_summary)
    scope_items = _extract_text_list(_safe_get(cs, "scope_items") or [])
    constraints = _extract_text_list(_safe_get(cs, "constraints") or [])

    # Build evidence maps from entries (entries have full structure; matched/missing are strings only).
    required = _safe_dict(_safe_get(_safe_dict(pcm), "required_activities"))
    entries = _safe_list(_safe_get(required, "entries"))

    matched_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"activities": set(), "basis": set(), "explanations": set()})
    missing_map: Dict[str, str] = {}
    for entry in entries:
        ent = _safe_dict(entry) if not isinstance(entry, dict) else entry
        key = _canonical_text(_safe_str(_safe_get(ent, "requirement")))
        if not key:
            continue
        status = _safe_get(ent, "status")
        if status == "FOUND":
            mpa = _safe_get(ent, "matched_programme_activities")
            activities_list = mpa if isinstance(mpa, list) else [mpa] if mpa else []
            for act in activities_list:
                if act:
                    matched_map[key]["activities"].add(str(act))
            basis = _safe_get(ent, "matching_basis")
            if basis:
                matched_map[key]["basis"].add(str(basis))
            expl = _safe_get(ent, "matching_explanation")
            if expl:
                matched_map[key]["explanations"].add(str(expl))
        else:
            if key not in missing_map:
                missing_map[key] = _safe_str(_safe_get(ent, "matching_explanation"), "No programme activity recorded for this obligation.")

    # Build programme activities list for governance evidence lookup
    ps = _safe_dict(programme_summary)
    programme_activities: List[str] = []
    for item in _safe_list(_safe_get(ps, "activities")):
        it = _safe_dict(item) if not isinstance(item, dict) else item
        name = _safe_get(it, "name") or _safe_get(it, "task_name") or _safe_get(it, "activity_name")
        if name:
            programme_activities.append(str(name).strip())
    for item in _safe_list(_safe_get(ps, "critical_path")):
        it = _safe_dict(item) if not isinstance(item, dict) else item
        name = _safe_get(it, "name")
        if name:
            programme_activities.append(str(name).strip())
    seen = set()
    ordered_programme_activities: List[str] = []
    for name in programme_activities:
        if name and name not in seen:
            ordered_programme_activities.append(name)
            seen.add(name)

    scope_rows: List[Dict[str, Any]] = []
    for scope_text in scope_items:
        canonical = _canonical_text(scope_text)
        classification = _classify_scope_item(scope_text)
        row_status: str
        programme_evidence: List[str] = []
        notes_parts: List[str] = []

        evidence_role = "Scope alignment"

        if classification == SCOPE_ASSURANCE_QUALITY:
            row_status = COVERAGE_ASSURANCE
            notes_parts.append("Addressed through standards, design assurance, and PM controls.")

        elif classification == SCOPE_GOVERNANCE_APPROVAL:
            gov_evidence = _find_governance_evidence(scope_text, ordered_programme_activities)
            if gov_evidence:
                row_status = COVERAGE_IMPLICIT
                programme_evidence = list(gov_evidence)
                notes_parts.append("Milestones, approval activities, or review steps are shown in the programme.")
            else:
                row_status = COVERAGE_IMPLICIT
                notes_parts.append("This obligation is typically managed through governance rather than programme logic.")

        else:
            # ACTIVITY_DELIVERABLE: distinguish explicit (exact match) vs implicit (token-overlap) coverage
            evidence: List[str] = []
            basis_set: set = set()
            expl_set: set = set()
            exact_match = canonical in matched_map
            if exact_match:
                evidence = list(matched_map[canonical]["activities"])
                basis_set = matched_map[canonical]["basis"]
                expl_set = matched_map[canonical]["explanations"]
            if not evidence:
                scope_tokens = _tokenise(scope_text)
                for req_key, data in matched_map.items():
                    req_tokens = _tokenise(req_key)
                    if scope_tokens & req_tokens:
                        evidence.extend(data["activities"])
                        basis_set |= data["basis"]
                        expl_set |= data["explanations"]
                evidence = sorted(set(evidence))

            if evidence:
                row_status = COVERAGE_EXPLICIT if exact_match else COVERAGE_IMPLICIT
                programme_evidence = evidence
                basis = ", ".join(sorted(basis_set)) or "semantic intent"
                explanation = "; ".join(sorted(expl_set))
                notes_parts.append(f"Match recorded on a {basis} basis.")
                if explanation:
                    notes_parts.append(explanation)
            elif canonical in missing_map:
                row_status = COVERAGE_NONE
                notes_parts.append(missing_map[canonical] or "No programme activity recorded for this obligation.")
            else:
                row_status = COVERAGE_NONE
                notes_parts.append("No programme activity recorded for this obligation.")

        # Confidence band: descriptive only; does not affect acceptability.
        if row_status == COVERAGE_EXPLICIT:
            confidence_band = CONFIDENCE_HIGH
        elif row_status in (COVERAGE_IMPLICIT, COVERAGE_ASSURANCE):
            confidence_band = CONFIDENCE_MODERATE
        else:
            confidence_band = CONFIDENCE_JUDGEMENT_REQUIRED

        scope_rows.append({
            "contract_scope": scope_text,
            "programme_activities": list(programme_evidence),
            "representation_status": row_status,
            "evidence_role": evidence_role,
            "notes": " ".join(notes_parts).strip(),
            "confidence_band": confidence_band,
        })

    # Activity load transparency: count how many scope obligations each programme activity supports
    activity_load: Dict[str, int] = defaultdict(int)
    for row in scope_rows:
        for act in row.get("programme_activities", []) or []:
            if act:
                activity_load[str(act)] += 1
    activity_load_notes: List[str] = []
    for act, count in sorted(activity_load.items(), key=lambda x: -x[1]):
        if count > ACTIVITY_LOAD_THRESHOLD:
            activity_load_notes.append(
                f'"{act}" supports several contract requirements and may benefit from additional programme detail as the project develops.'
            )

    scope_counts = Counter(row["representation_status"] for row in scope_rows)
    if scope_items:
        parts: List[str] = []
        for label in (COVERAGE_EXPLICIT, COVERAGE_IMPLICIT, COVERAGE_ASSURANCE, COVERAGE_NONE):
            if scope_counts.get(label):
                parts.append(f"{scope_counts[label]} {label.lower()}")
        scope_summary = (
            "This assessment is based on the actual contract scope and the actual activities in the submitted programme, as listed above. "
            "Not all contract scope items are expected to appear as individual programme activities; some relate to quality, compliance, or assurance and are normally managed through standards, reviews, and controls."
        )
        if parts:
            scope_summary += " " + "; ".join(parts) + "."
    else:
        scope_summary = "No scope items were extracted from the contract; confirm scope alignment manually."

    # Constraint coverage: use direct evidence from programme activities (ordered_programme_activities already built above).
    constraint_rows: List[Dict[str, Any]] = []
    for constraint_text in constraints:
        evidence: List[str] = []
        lower_constraint = constraint_text.lower()
        for activity_name in ordered_programme_activities:
            if lower_constraint in activity_name.lower():
                evidence.append(activity_name)
        if not evidence:
            constraint_tokens = _tokenise(constraint_text)
            if constraint_tokens:
                for activity_name in ordered_programme_activities:
                    if _tokenise(activity_name) & constraint_tokens:
                        evidence.append(activity_name)
        evidence = sorted(set(evidence))
        if evidence:
            handling = "Explicit in programme"
            programme_evidence = ", ".join(evidence[:3]) + ("…" if len(evidence) > 3 else "")
            confidence_band = CONFIDENCE_HIGH
        else:
            handling = "Implicitly managed"
            programme_evidence = "— (managed through general site controls)"
            confidence_band = CONFIDENCE_MODERATE
        constraint_rows.append({
            "constraint": constraint_text,
            "programme_evidence": programme_evidence,
            "handling": handling,
            "evidence_role": "Constraint alignment",
            "confidence_band": confidence_band,
        })

    explicit_constraints = sum(1 for row in constraint_rows if row["handling"] == "Explicit in programme")
    implicit_constraints = len(constraint_rows) - explicit_constraints
    if constraints:
        constraint_summary = (
            "This assessment is based on the actual constraints identified in the contract and the programme activities shown above. "
            f"{explicit_constraints} constraint(s) are explicitly named in the programme; {implicit_constraints} rely on implicit management or operational controls."
        )
    else:
        constraint_summary = "No explicit contract constraints were extracted; confirm how constraints are managed."

    # Report reflects validator result exactly. Do not recalculate or soften acceptability.
    vs = _safe_dict(validation_summary)
    failure_reasons = _safe_list(_safe_get(vs, "acceptability_failure_reasons"))
    # Tripwire: report must never say "acceptable" while failure reasons exist.
    if _safe_get(vs, "acceptability_status") == "ACCEPTABLE" and failure_reasons:
        raise RuntimeError(
            "Report contradiction: cannot output 'acceptable' while acceptability_failure_reasons is non-empty. Refusing to generate report."
        )
    # Fatal guard: if report would say "acceptable" while any mandatory obligation is not aligned, crash.
    if _safe_get(vs, "acceptability_status") == "ACCEPTABLE":
        not_rep = _safe_list(_safe_get(scope_coverage, "obligations_not_represented_but_mandatory"))
        if _safe_get(scope_coverage, "obligation_entities_used") and not_rep:
            raise RuntimeError(
                "Report contradiction: cannot output 'acceptable' while mandatory obligations are not represented. "
                "obligations_not_represented_but_mandatory is non-empty. Refusing to generate report."
            )
        acceptability_clarification = (
            "The programme aligns with the contract scope and constraints and is acceptable at this stage."
        )
    else:
        reason = failure_reasons[0] if failure_reasons else "one or more mandatory obligations are not represented"
        acceptability_clarification = (
            f"The programme is not acceptable at this stage. {reason}. "
            "This remains a Clause 31 programme completeness issue rather than a scope misalignment."
        )

    reassurance = (
        "The tables above show the exact contract wording and the programme evidence used in this assessment. "
        "The outstanding actions relate to programme completeness, not a misunderstanding of scope or constraints."
    )

    scope_client_note = (
        "Not all contract scope items are expected to appear as individual programme activities. "
        "Some requirements relate to quality, compliance, or assurance and are normally managed through standards, reviews, and controls."
    )

    # When obligation_entities_used: list evidenced, explicit assumption (client_responsibility/out_of_scope), covered_by_later_submission (advisory only), not-represented-but-mandatory, assurance-based.
    obligations_evidenced_list: List[Dict[str, Any]] = []
    obligations_explicit_assumption_list: List[Dict[str, Any]] = []
    obligations_covered_by_later_submission_list: List[Dict[str, Any]] = []
    obligations_not_represented_but_mandatory_list: List[Dict[str, Any]] = []
    obligations_assurance_based_list: List[Dict[str, Any]] = []
    if _safe_get(scope_coverage, "obligation_entities_used"):
        for ob in _safe_list(_safe_get(scope_coverage, "obligations_evidenced")):
            o = _safe_dict(ob)
            if o:
                obligations_evidenced_list.append({
                    "id": _safe_str(_safe_get(o, "id")),
                    "text": _safe_str(_safe_get(o, "original_contract_text"))[:120] + ("…" if len(_safe_str(_safe_get(o, "original_contract_text"))) > 120 else ""),
                })
        for ob in _safe_list(_safe_get(scope_coverage, "obligations_explicit_assumption")):
            o = _safe_dict(ob)
            if o:
                obligations_explicit_assumption_list.append({
                    "id": _safe_str(_safe_get(o, "id")),
                    "text": _safe_str(_safe_get(o, "original_contract_text"))[:120] + ("…" if len(_safe_str(_safe_get(o, "original_contract_text"))) > 120 else ""),
                    "exemption_reason": _safe_str(_safe_get(o, "exemption_reason")),
                })
        for ob in _safe_list(_safe_get(scope_coverage, "obligations_covered_by_later_submission")):
            o = _safe_dict(ob)
            if o:
                obligations_covered_by_later_submission_list.append({
                    "id": _safe_str(_safe_get(o, "id")),
                    "text": _safe_str(_safe_get(o, "original_contract_text"))[:120] + ("…" if len(_safe_str(_safe_get(o, "original_contract_text"))) > 120 else ""),
                })
        for ob in _safe_list(_safe_get(scope_coverage, "obligations_not_represented_but_mandatory")):
            o = _safe_dict(ob)
            if o:
                obligations_not_represented_but_mandatory_list.append({
                    "id": _safe_str(_safe_get(o, "id")),
                    "text": _safe_str(_safe_get(o, "original_contract_text"))[:120] + ("…" if len(_safe_str(_safe_get(o, "original_contract_text"))) > 120 else ""),
                })
        for ob in _safe_list(_safe_get(scope_coverage, "obligations_assurance_based")):
            o = _safe_dict(ob)
            if o:
                obligations_assurance_based_list.append({
                    "id": _safe_str(_safe_get(o, "id")),
                    "text": _safe_str(_safe_get(o, "original_contract_text"))[:120] + ("…" if len(_safe_str(_safe_get(o, "original_contract_text"))) > 120 else ""),
                })

    return {
        "section_intro": "How the programme reflects the contract scope and constraints",
        "scope_client_note": scope_client_note,
        "scope_summary": scope_summary,
        "scope_rows": scope_rows,
        "activity_load_notes": activity_load_notes,
        "obligations_evidenced_list": obligations_evidenced_list,
        "obligations_explicit_assumption_list": obligations_explicit_assumption_list,
        "obligations_covered_by_later_submission_list": obligations_covered_by_later_submission_list,
        "obligations_not_represented_but_mandatory_list": obligations_not_represented_but_mandatory_list,
        "obligations_assurance_based_list": obligations_assurance_based_list,
        "constraint_summary": constraint_summary,
        "constraint_rows": constraint_rows,
        "acceptability_clarification": acceptability_clarification,
        "reassurance": reassurance,
    }


def _section_c(
    alignment: Dict[str, Any],
    contract_summary: Dict[str, Any],
    programme_summary: Dict[str, Any],
) -> Dict[str, Any]:
    """Section C — Programme vs Contract Dates."""
    align = _safe_dict(alignment)
    cs = _safe_dict(contract_summary)
    ps = _safe_dict(programme_summary)
    start = _safe_dict(_safe_get(align, "starting_date"))
    completion = _safe_dict(_safe_get(align, "completion_date"))
    possession = _safe_dict(_safe_get(align, "possession_dates"))

    start_val = _safe_dict(_safe_get(cs, "starting_date"))
    comp_val = _safe_dict(_safe_get(cs, "completion_date"))
    contract_start = _safe_str(_safe_get(start_val, "value")) or _safe_str(_safe_get(start, "contract"), "—")
    contract_completion = _safe_str(_safe_get(comp_val, "value")) or _safe_str(_safe_get(completion, "contract"), "—")
    contract_access = _safe_str(_safe_get(possession, "contract"), "—")
    prog_start = _safe_str(_safe_get(start, "programme")) or _safe_str(_safe_get(ps, "programme_start_date"), "—")
    prog_completion = _safe_str(_safe_get(completion, "programme")) or _safe_str(_safe_get(ps, "programme_finish_date"), "—")

    variance_explanation = _safe_str(_safe_get(completion, "reason"))
    if _safe_get(start, "reason"):
        variance_explanation = (variance_explanation + " " + _safe_str(_safe_get(start, "reason"))).strip()
    if _safe_get(possession, "reason"):
        variance_explanation = (variance_explanation + " " + _safe_str(_safe_get(possession, "reason"))).strip()
    if not variance_explanation:
        variance_explanation = "No material variance; or variance explained by working-day/calendar rules (e.g. 5-day schedule, weekend completion). See Section B for full date logic where relevant."

    intro = "The table below compares key contract dates with the programme. Any variance is explained in the notes; full date logic is set out in Section B."
    return {
        "section_intro": intro,
        "rows": [
            {"item": "Contract access / possession", "contract": contract_access, "programme": "—", "notes": _safe_str(_safe_get(possession, "reason"), "—")},
            {"item": "Contract start", "contract": contract_start, "programme": prog_start, "notes": _safe_str(_safe_get(start, "reason"), "—")},
            {"item": "Contract completion", "contract": contract_completion, "programme": prog_completion, "notes": _safe_str(_safe_get(completion, "reason"), "—")},
        ],
        "variance_explanation": variance_explanation,
    }


def _section_d(pcm: Dict[str, Any], alignment: Dict[str, Any]) -> Dict[str, Any]:
    """Section D — Required Activities & Completion Gates."""
    p = _safe_dict(pcm)
    if not p:
        return {
            "section_intro": "Required activities and completion gates from the Programme Compliance Model (when present) are set out below with evidence of satisfaction or otherwise.",
            "required_activities_table": [],
            "completion_gates_table": [],
            "summary": "No Programme Compliance Model data.",
        }

    required = _safe_dict(_safe_get(p, "required_activities"))
    gates = _safe_dict(_safe_get(p, "completion_and_takeover_gates"))

    # Single source of truth: these three values are the only counts we show. They must reconcile.
    total_contract = _safe_get(required, "total_contract_required_activities") or _safe_get(required, "total_required_activities") or 0
    expected_now_total = _safe_get(required, "expected_now_total") or 0
    expected_now_found = _safe_get(required, "expected_now_found") or _safe_get(required, "matched_required_activities") or 0
    expected_now_missing = _safe_get(required, "expected_now_missing") or _safe_get(required, "missing_required_activities") or 0
    expected_later_total = _safe_get(required, "expected_later_total") or max(0, total_contract - expected_now_total)
    expected_later_found = _safe_get(required, "expected_later_found") or 0
    expected_later_missing = _safe_get(required, "expected_later_missing") or 0

    # User-facing summary: same text produced by validator
    required_summary_text = _safe_str(_safe_get(required, "summary"))
    if not required_summary_text:
        if total_contract > 0:
            required_summary_text = (
                f"Contract obligations: {total_contract} activities (expected now: {expected_now_total}, expected later: {expected_later_total}). "
                f"Expected-now found: {expected_now_found}/{expected_now_total}; missing: {expected_now_missing}. "
                "Expected-later activities remain informational and are listed below."
            )
        else:
            required_summary_text = "No contract required activities were identified."

    stage_label = _safe_get(p, "programme_stage_label") or _safe_get(p, "programme_stage") or "UNKNOWN"
    context_contract_type = _safe_get(p, "contract_type") or "UNKNOWN"
    programme_intent = _safe_get(p, "programme_intent") or "mixed"
    expectation_policy = _safe_str(_safe_get(p, "required_activity_expectation_policy"))
    stage_intro_parts = []
    stage_intro_parts.append(f"Context: Contract type = {context_contract_type}; Programme intent = {programme_intent}.")
    if stage_label and stage_label != "":
        stage_intro_parts.append(f"Programme stage: {stage_label}.")
    if expectation_policy:
        stage_intro_parts.append(expectation_policy)

    # One-to-one list: built only from matched + missing (the same list that was checked). No excluded, no diagnostics.
    entries = _safe_list(_safe_get(required, "entries"))
    required_rows = []
    for entry in entries:
        entry = _safe_dict(entry) if not isinstance(entry, dict) else entry
        requirement = _safe_str(_safe_get(entry, "requirement"))
        expectation = _safe_get(entry, "expectation") or EXPECTED_LATER
        expectation_text = "Required at this stage" if expectation == EXPECTED_NOW else "Required later in the contract"
        status = _safe_get(entry, "status") or "NOT_FOUND"
        shown_text = "Included in the programme" if status == "FOUND" else "Not included in the programme"
        mpa = _safe_get(entry, "matched_programme_activities")
        matched_programme_activities = mpa if isinstance(mpa, list) else []
        notes_parts: List[str] = []
        if matched_programme_activities:
            notes_parts.append(f"Shown as: {', '.join(str(x) for x in matched_programme_activities)}.")
        if _safe_get(entry, "matching_explanation"):
            notes_parts.append(str(_safe_get(entry, "matching_explanation")))
        if _safe_get(entry, "expectation_reason"):
            notes_parts.append(str(_safe_get(entry, "expectation_reason")))
        if not notes_parts:
            notes_parts.append("No additional notes.")
        # Confidence band: descriptive only; does not affect acceptability.
        if status == "FOUND":
            basis = _safe_get(entry, "matching_basis") or ""
            confidence_band = CONFIDENCE_HIGH if (basis and "explicit" in str(basis).lower()) else CONFIDENCE_MODERATE
        else:
            confidence_band = CONFIDENCE_JUDGEMENT_REQUIRED
        required_rows.append({
            "contract_activity": requirement,
            "when_required": expectation_text,
            "shown_in_programme": shown_text,
            "notes": " ".join(notes_parts).strip(),
            "evidence_role": "Programme acceptability",
            "confidence_band": confidence_band,
        })

    gate_rows = []
    for g in _safe_list(_safe_get(gates, "matched")):
        ag = str(g) if not isinstance(g, dict) else _safe_str(_safe_get(g, "activity_or_gate"), str(g))
        gate_rows.append({
            "activity_or_gate": ag,
            "status": "Included in the programme",
            "evidence": "Completion control is shown in the schedule.",
            "evidence_role": "Programme acceptability",
        })
    for g in _safe_list(_safe_get(gates, "missing")):
        ag = str(g) if not isinstance(g, dict) else _safe_str(_safe_get(g, "activity_or_gate"), str(g))
        gate_rows.append({
            "activity_or_gate": ag,
            "status": "Not included in the programme",
            "evidence": "Add this completion control so the handover path is clear.",
            "evidence_role": "Programme acceptability",
        })

    intro = "Required activities and completion gates from the contract are set out below."
    if stage_intro_parts:
        intro = " ".join(stage_intro_parts) + " " + intro
    gates_summary = _safe_str(_safe_get(gates, "summary"))
    summary = (required_summary_text or "") + " " + gates_summary
    return {
        "section_intro": intro,
        "required_activities_table": required_rows,
        "completion_gates_table": gate_rows,
        "total_required_activities": total_contract,
        "matched_required_activities": expected_now_found,
        "missing_required_activities": expected_now_missing,
        "expected_now_total": expected_now_total,
        "expected_now_found": expected_now_found,
        "expected_now_missing": expected_now_missing,
        "expected_later_total": expected_later_total,
        "expected_later_found": expected_later_found,
        "expected_later_missing": expected_later_missing,
        "required_summary": required_summary_text,
        "gates_summary": gates_summary,
        "summary": summary.strip() or "See tables above.",
        "programme_stage": stage_label,
        "programme_stage_reasoning": _safe_str(_safe_get(p, "programme_stage_reasoning")),
        "programme_stage_signals": _safe_dict(_safe_get(p, "programme_stage_signals")),
        "programme_stage_signals_used": _safe_list(_safe_get(p, "programme_stage_signals_used")),
        "programme_stage_signals_ignored": _safe_list(_safe_get(p, "programme_stage_signals_ignored")),
    }


def _section_e(
    programme_summary: Dict[str, Any],
    validation_summary: Dict[str, Any],
    risks: Dict[str, Any],
) -> Dict[str, Any]:
    """Section E — Programme confidence and observations for follow-up."""
    ps = _safe_dict(programme_summary)
    observations: List[str] = []
    oos = _safe_list(_safe_get(ps, "out_of_sequence_activities"))
    if oos:
        observations.append(f"{len(oos)} activities start before their predecessors finish; review these logic links to keep the plan realistic.")
    nfl = _safe_list(_safe_get(ps, "negative_float_list"))
    if nfl:
        observations.append(f"{len(nfl)} activities carry negative float, signalling the schedule is running late and may need recovery actions.")
    le = _safe_list(_safe_get(ps, "logic_errors"))
    if le:
        observations.append(f"{len(le)} logic links appear broken or incomplete; reconnect them so the programme remains defensible.")
    if _safe_get(ps, "circular_dependencies"):
        observations.append("Circular logic is present; remove loops so progress can be monitored clearly.")
    float_dist = _safe_dict(_safe_get(ps, "total_float_distribution"))
    if float_dist:
        observations.append(
            "Float profile – zero: {zero}, low: {low_positive}, medium: {medium_positive}, high: {high_positive}. "
            "Use this to confirm that float is concentrated where you expect.".format(**{k: _safe_get(float_dist, k) or 0 for k in [
                "zero", "low_positive", "medium_positive", "high_positive"
            ]})
        )

    rsk = _safe_dict(risks)
    supportive_notes: List[str] = []
    for severity in ("critical", "major", "minor"):
        for r in _safe_list(_safe_get(rsk, severity)):
            r = _safe_dict(r) if not isinstance(r, dict) else r
            summary = _safe_get(r, "summary")
            next_step = _safe_get(r, "next_step")
            if summary or next_step:
                supportive_notes.append(f"{summary} {next_step}".strip())

    vs = _safe_dict(validation_summary)
    # Advisory only; must not imply that confidence/observations affect acceptability.
    intro = (
        "Confidence in the programme remains under review. The points below are advisory only and do not determine acceptability; they should be worked through so the plan stays dependable."
    )
    return {
        "section_intro": intro,
        "observations": observations,
        "supportive_notes": supportive_notes,
        "quality_commentary": _safe_str(_safe_get(vs, "quality_score_explanation")),
    }


def _section_f(alignment: Dict[str, Any]) -> Dict[str, Any]:
    """Section F — Additional information noted for completeness."""
    align = _safe_dict(alignment)
    information_items: List[str] = []
    for key, label in [
        ("weather_alignment", "Weather data arrangements"),
        ("programme_submission", "Programme submission and review cycle"),
    ]:
        entry = _safe_dict(_safe_get(align, key))
        if entry and _safe_str(_safe_get(entry, "importance_tier")).endswith("INFORMATIONAL"):
            reason = _safe_str(_safe_get(entry, "reason"), "Recorded for information; no immediate action required.")
            information_items.append(f"{label}: {reason}")
    if not information_items:
        information_items.append("No additional information items were noted for this review.")

    intro = "The following points are recorded for completeness. They do not affect the acceptance decision but may be useful for reference."
    return {
        "section_intro": intro,
        "information_items": information_items,
    }


def _section_g(alignment: Dict[str, Any], nec_detailed: Dict[str, Any]) -> Dict[str, Any]:
    """Section G — Where the comparisons came from."""
    align = _safe_dict(alignment)
    nec = _safe_dict(nec_detailed)
    mapping_rows: List[Dict[str, str]] = []
    for key in ["starting_date", "completion_date", "possession_dates", "key_dates", "delay_damages_alignment", "weather_alignment"]:
        entry = _safe_dict(_safe_get(align, key))
        if entry:
            mapping_rows.append({
                "finding_or_check": key.replace("_", " ").title(),
                "source_clause": _safe_str(_safe_get(entry, "source_clause"), "Contract reference"),
                "source_type": _safe_str(_safe_get(entry, "source_type")),
                "validation_basis": _safe_str(_safe_get(entry, "validation_basis")),
            })

    pcm = _safe_dict(_safe_get(align, "programme_compliance_model"))
    if pcm:
        for subkey in ["required_activities", "completion_and_takeover_gates"]:
            sub = _safe_dict(_safe_get(pcm, subkey))
            if sub:
                mapping_rows.append({
                    "finding_or_check": subkey.replace("_", " ").title(),
                    "source_clause": _safe_str(_safe_get(sub, "source_clause"), "Programme requirements"),
                    "source_type": _safe_str(_safe_get(sub, "source_type")),
                    "validation_basis": _safe_str(_safe_get(sub, "validation_basis")),
                })

    methodology = (
        "We compared each key contract requirement with the programme to confirm whether it is represented. "
        "Where the contract was silent, we noted the assumption used so it can be reviewed by the Project Manager."
    )
    intro = "Each comparison is linked to its contract reference so you can trace where the expectation came from if you need to discuss it."
    return {
        "section_intro": intro,
        "mapping_table": mapping_rows,
        "methodology_summary": methodology,
        "nec_detailed_clauses": list(nec.keys()) if nec else [],
    }
