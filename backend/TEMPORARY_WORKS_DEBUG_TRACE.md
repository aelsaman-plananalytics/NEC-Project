# Temporary Works — End-to-end debug trace and fix

## 1. Contract analysis

**Where "Temporary Works" could be extracted:**

- **HybridAIExtractor** (`backend/app/contract_parser/hybrid_ai_extractor.py`): Returns `scope_items` from LLM JSON. The contract text "Review draft temporary works schedule and identify significant temporary works designs..." is extracted as a scope item (confirmed in analysis JSON). There is no deterministic extraction of the short phrase "Temporary Works".
- **UnifiedExtractor**: Used in analyze_contract for dates/clauses; its output is **not** used for `scope_items`. So it does not feed obligations.
- **PhraseExtractor**: Not in the analyze_contract flow for scope_items.
- **Fixed ontology / taxonomy**: `section_extractor.py` and `ontology.py` mention "temporary works" in patterns/lists but are not used to populate `scope_items` in the analyze_contract path.

**Is "Temporary Works" guaranteed in contract_data["scope_items"]?**  
No. The only scope item that mentions temporary works is the long LLM-extracted sentence. That **does** appear in `scope_items` when the LLM returns it, but there is no guarantee of a standalone "Temporary Works" item. It **depends on the LLM response**.

---

## 2. Obligation construction

**In `build_obligation_entities()` (`backend/app/p6_engine/obligation_entities.py`):**

**Sources that contribute to `raw`:**

1. `contract_data["scope_items"]` — each item → (text, clause_ref, FACET_SCOPE, mandatory, scope_class). `mandatory` = item["mandatory_for_acceptance"] if present, else `(classification == ACTION_REQUIRED)`. `classification = classify_scope_obligation(text)` (ASSURANCE_REQUIRED if pattern matches "review", "assurance", etc.).
2. PCM: `programme_duties` / `required_activities` / `programme_requirements` → FACET_PROGRAMME_DUTY.
3. `contract_data["constraints"]` + PCM `sequencing_and_timing_constraints` → FACET_TIMING.
4. PCM `programme_governance_and_acceptance_rules` + `completion_and_takeover_gates` → FACET_GOVERNANCE.
5. **Injection:** If no existing raw entry has signature `_obligation_signature("Temporary Works")` (= `"temporary works"`), then `add("Temporary Works", "", FACET_SCOPE, True, SCOPE_CLASSIFICATION_ACTION_REQUIRED)`.

Obligations are built **only** from the above (scope_items, PCM, constraints, governance, and the Temporary Works injection). No other source.

**Can "Temporary Works" be completely absent from obligation_entities?**  
Yes. **If validation uses `contract_data["obligation_entities"]` that was loaded from a JSON file** (saved at analysis time) **and never rebuilds it**, then the list is whatever was produced when that JSON was created. If that was before the injection was added, or if obligation_entities were never built from that contract_data, the "Temporary Works" obligation will be absent.

---

## 3. Validation

**In `_validate_obligation_entities()`:**  
It only processes `obligations_list = entities.get("obligations") or []`. It does **not** check for "Temporary Works" if it is missing from that list; there is **no** fallback rule that adds or enforces Temporary Works independently. So if the obligation is not in `obligations_list`, it is never validated and never blocks acceptability.

---

## 4. Reporting

The report is built from `scope_coverage` (scope_evidence_table, obligations_report, etc.), which comes from `_validate_obligation_entities`. So the report can **only** show obligations that exist in scope_coverage. Nothing in the report layer can add or resurrect a missing obligation.

---

## 5. Root cause (one only)

**Validation uses pre-built `obligation_entities` from the loaded contract JSON and never rebuilds them.**

- At **analysis** time, `build_frozen_requirements(response_data)` runs and writes `obligation_entities` into the saved JSON.
- At **validation** time, the router loads that JSON into `contract_data` and passes it to the validator. The validator uses `contract_data["obligation_entities"]` as-is and **does not** call `build_frozen_requirements` or `build_obligation_entities`.
- So if the saved JSON was produced **before** the "Temporary Works" injection was added to `build_obligation_entities`, the loaded `obligation_entities` do **not** contain the mandatory "Temporary Works" obligation. The validator then has zero mandatory obligations related to Temporary Works, so programmes without any Temporary Works WBS/activities can still be marked "Acceptable at this stage".

**Why both programmes (with and without Temporary Works activities) are acceptable:**  
Because the obligation list used at validation time does not include a mandatory "Temporary Works" obligation. So acceptability is not conditioned on it; the WBS rule in the validator only runs when an obligation with text "Temporary Works" exists.

---

## 6. Fix (minimum deterministic)

**Goal:** "Temporary Works" always exists as a mandatory scope obligation, appears in obligation_entities and in scope & constraints reporting, and acceptability FAILs if no Temporary Works WBS/activity exists.

**Change:** Rebuild obligation_entities at validation time so that the current `build_obligation_entities` logic (including the "Temporary Works" injection) always runs.

---

### Deliverables

**Exact file name:**  
`backend/app/routers/validate_programme.py`

**Exact function:**  
`validate_programme` (the POST handler). The insertion is in the same flow that loads `contract_data`, **after** the "Invalid contract JSON" check and **before** loading the XER and calling `_run_programme_validation`.

**Exact code insertion:**

1. **Import** (top of file, with other app imports):
```python
from app.p6_engine.frozen_requirements import build_frozen_requirements
```

2. **Block** after the invalid-JSON check and before `print(f"[VALIDATE_PROGRAMME] Loading XER file: ..."`):
```python
        # Rebuild obligation_entities at validation time so current logic (e.g. mandatory "Temporary Works")
        # always applies. Stale analysis JSON may have been produced before that logic existed.
        try:
            frozen = build_frozen_requirements(contract_data)
            contract_data["obligation_entities"] = frozen.get("obligation_entities", {})
            contract_data["frozen_requirements"] = frozen.get("frozen_requirements", [])
        except Exception as e:
            contract_data["obligation_entities"] = {"obligations": [], "validation_error": str(e)}
            contract_data["frozen_requirements"] = []
```

**Effect:**  
Every validation run rebuilds obligation_entities from the current `contract_data` (scope_items, PCM, constraints, etc.) using `build_obligation_entities`, which includes the mandatory "Temporary Works" injection. So:

- "Temporary Works" is always present as a mandatory scope obligation (unless already merged by signature).
- It appears in obligation_entities, obligations_report, and scope_evidence_table.
- The existing rule in the validator requires ≥1 activity whose WBS path contains "Temporary Works" for that obligation to be evidenced; otherwise it remains not aligned and acceptability fails.

No heuristics, no weakening of acceptability, no reliance on AI to extract "Temporary Works"; one obligation source of truth built at validation time.
