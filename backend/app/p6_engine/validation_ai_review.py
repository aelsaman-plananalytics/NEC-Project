"""
AI review of programme vs contract validation.

Uses an LLM (OpenAI/Azure) to confirm or correct misunderstandings in the
rule-based validation—e.g. "28 March 2023" vs "2023-03-28" are the same date;
programme completion should be the project end milestone, not a gate key.

Also provides optional LLM-based obligation evidence: when USE_LLM_OBLIGATION_EVIDENCE
is set, the engineering model decides whether programme activities evidence each
contract obligation (instead of phrase-based matching).
"""

import json
import os
from typing import Dict, List, Any, Optional, Tuple

try:
    from openai import AzureOpenAI, OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AzureOpenAI = None
    OpenAI = None


def review_validation(
    contract_summary: Dict[str, Any],
    programme_summary: Dict[str, Any],
    alignment: Dict[str, Any],
    validation_summary: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Optional AI review of validation output.

    Confirms or corrects misunderstandings (e.g. date format equivalence,
    which milestone is project completion). If LLM is unavailable or fails,
    returns { "skipped": true, "reason": "..." }.
    """
    result: Dict[str, Any] = {
        "confirmed": [],
        "corrections": [],
        "notes": [],
        "skipped": False,
        "reason": "",
    }
    client = _get_client()
    if not client or not OPENAI_AVAILABLE:
        result["skipped"] = True
        result["reason"] = "AI review skipped: OpenAI not available or API key not set."
        return result

    model = _get_model()
    prompt = _build_review_prompt(contract_summary, programme_summary, alignment, validation_summary)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an NEC contract and programme validation reviewer. You confirm or correct rule-based validation results. Return ONLY valid JSON with keys: confirmed (list of strings), corrections (list of {item, correction, reason}), notes (list of strings)."
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        text = (response.choices[0].message.content or "").strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text)
        result["confirmed"] = parsed.get("confirmed", []) if isinstance(parsed.get("confirmed"), list) else []
        result["corrections"] = parsed.get("corrections", []) if isinstance(parsed.get("corrections"), list) else []
        result["notes"] = parsed.get("notes", []) if isinstance(parsed.get("notes"), list) else []
        return result
    except Exception as e:
        result["skipped"] = True
        result["reason"] = f"AI review failed: {str(e)}"
        return result


def evaluate_obligation_programme_exemption_llm(
    obligation_text: str,
    contract_type_context: str = "NEC",
) -> Tuple[bool, str]:
    """
    Ask the LLM: Is this obligation normally expected to be explicitly represented
    in a construction-stage NEC Clause 31 programme for this contract type?
    Returns (exempt, reason). exempt=True means NO, not expected on programme → may set aligned with llm_exemption.
    When LLM unavailable or fails, returns (False, "").
    """
    client = _get_client()
    if not client or not OPENAI_AVAILABLE:
        return (False, "")
    model = _get_model()
    prompt = f"""Contract obligation: "{obligation_text[:700]}"

Contract context: {contract_type_context}.

Question: Is this obligation normally expected to be explicitly represented in a construction-stage NEC Clause 31 programme (e.g. as a named activity, milestone, or deliverable)?

Answer NO (exempt) only if the obligation is typically satisfied by governance, assurance, or standards rather than by a specific programme activity (e.g. quality assurance, professional judgement, coordination that does not require a programme line).

Return JSON only: {{ "expected_on_programme": true or false, "reason": "One short sentence explaining why." }}

If expected_on_programme is false, the obligation is treated as exempt from programme representation (reason explains why)."""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        text = (response.choices[0].message.content or "{}").strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text)
        expected = bool(parsed.get("expected_on_programme", True))
        reason = str(parsed.get("reason", "")).strip() or "LLM determined this obligation is not expected to be explicitly represented on the programme."
        # exempt = not expected on programme
        exempt = not expected
        return (exempt, reason)
    except Exception:
        return (False, "")


def evaluate_obligation_evidence_llm(
    obligation_text: str,
    activity_list: List[Tuple[str, str]],
) -> Tuple[bool, List[str]]:
    """
    Use the engineering model (LLM) to decide if the obligation is evidenced
    by any of the programme activities. Returns (evidenced, activity_ids).
    When LLM is unavailable or fails, returns (False, []).
    """
    client = _get_client()
    if not client or not OPENAI_AVAILABLE:
        return (False, [])
    model = _get_model()
    # activity_list is [(id, name), ...]; cap to avoid token limit
    activities_str = "\n".join(f"- {aid}: {name}" for aid, name in activity_list[:80])
    prompt = f"""Contract obligation: "{obligation_text[:600]}"

Programme activities (id and name):
{activities_str}

Does the programme evidence this obligation? One or more activities may represent doing the requirement (or part of it). Consider semantic equivalence (e.g. "procure materials" evidences "procure in advance and store materials").
Return JSON only: {{ "evidenced": true or false, "activity_ids": ["id1", "id2"] }}"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        text = (response.choices[0].message.content or "{}").strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text)
        evidenced = bool(parsed.get("evidenced", False))
        ids = list(parsed.get("activity_ids", [])) if isinstance(parsed.get("activity_ids"), list) else []
        return (evidenced, ids)
    except Exception:
        return (False, [])


def _get_client():
    if not OPENAI_AVAILABLE:
        return None
    ai_mode = os.getenv("AI_MODE", "real").lower().strip()
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
    azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "")
    azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if (ai_mode == "azure" or (ai_mode == "real" and azure_endpoint and azure_api_key)) and azure_endpoint and azure_api_key and azure_deployment:
        try:
            return AzureOpenAI(
                api_key=azure_api_key,
                api_version=azure_api_version,
                azure_endpoint=azure_endpoint,
            )
        except Exception:
            pass
    if openai_key:
        try:
            return OpenAI(api_key=openai_key)
        except Exception:
            pass
    return None


def _get_model() -> str:
    if os.getenv("AI_MODE", "").lower() == "azure":
        return os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
    return os.getenv("OPENAI_VALIDATION_REVIEW_MODEL", "gpt-4o")


def _build_review_prompt(
    contract_summary: Dict[str, Any],
    programme_summary: Dict[str, Any],
    alignment: Dict[str, Any],
    validation_summary: Dict[str, Any],
) -> str:
    start_contract = (contract_summary.get("starting_date") or {}).get("value", "")
    start_prog = (alignment.get("starting_date") or {}).get("programme", "")
    start_status = (alignment.get("starting_date") or {}).get("status", "")
    comp_contract = (contract_summary.get("completion_date") or {}).get("value", "")
    comp_prog = (alignment.get("completion_date") or {}).get("programme", "")
    comp_status = (alignment.get("completion_date") or {}).get("status", "")
    prog_start = programme_summary.get("programme_start_date", "")
    prog_finish = programme_summary.get("programme_finish_date", "")
    overall = validation_summary.get("overall_status", "")
    start_outcome = (alignment.get("starting_date") or {}).get("outcome", "")
    comp_outcome = (alignment.get("completion_date") or {}).get("outcome", "")
    summary_explanation = validation_summary.get("summary_explanation", "")

    return f"""Review this programme vs contract validation and confirm or correct misunderstandings.

OUTCOMES (each check is classified): COMPLIANT, HARD_BREACH, SOFT_BREACH, or INTERPRETIVE. HARD_BREACH = unequivocal NEC non-compliance; TIER_3 (weather, payment) has zero score impact. Every failure must be explainable in NEC terms.

SCOPE OF VALIDATION (what the programme is marked on):
- Contract key DATES (starting date, completion date, key milestones).
- Activities that are SCOPE ITEMS, REQUIRED ACTIVITIES, and contract-mandated deliverables.
- NOT: weather schedules, payment terms, or other contract clauses that do not need to appear on the programme.

CONTRACT:
- Starting date: {start_contract}
- Completion date: {comp_contract}

PROGRAMME (from XER/TASK table):
- Programme start date: {prog_start}
- Programme finish date: {prog_finish}
- Alignment starting_date: {start_prog} (status: {start_status}, outcome: {start_outcome})
- Alignment completion_date: {comp_prog} (status: {comp_status}, outcome: {comp_outcome})

OVERALL: {overall}. {summary_explanation}

TASKS:
1. Confirm or correct: "28 March 2023" and "2023-03-28" are the same date (format difference only). If the engine marked them as mismatch, add a correction.
2. Confirm or correct: Programme completion for contract comparison should be the project end (Completion or Finish Milestone date), not a gate key or other milestone. If the engine used the wrong milestone, add a correction.
3. FIVE-DAY WORKWEEK: If the programme uses a standard 5-day worksheet/workweek schedule, the contract completion date falling on a WEEKEND (e.g. 31 March = Sunday) does not count as a working day. So programme completion on the NEXT WORKING DAY (e.g. 1 April Monday) is CORRECT and should be confirmed as aligned, not late. If the engine or user flagged this as an issue, add a correction or confirmation.
4. Add any other confirmations (what the engine got right) or corrections (misunderstandings) in one short line each.
5. Remember: not everything in the contract must appear on the programme—only dates, scope items, and required activities are what the programme is validated against. Weather data, payment terms, etc. are not programme requirements.

Return JSON only:
{{ "confirmed": ["list", "of", "correct", "findings"], "corrections": [{{"item": "starting_date", "correction": "Same date, format only", "reason": "28 March 2023 = 2023-03-28"}}], "notes": ["optional notes"] }}
"""
