# End-to-end trace: why "Temporary Works" does not appear in validation output

## 1. Contract analysis stage

### Occurrences of "Temporary Works" (case-insensitive)

| Location | Usage |
|----------|--------|
| **backend/app/contract_parser/section_extractor.py** (lines 332, 351) | Regex patterns `r'temporary works sequencing'` and `r'temporary works'` in a constraint-type taxonomy (key `"temp_works"`). Used for constraint classification in section-based extraction, **not** for scope_items in the analyze_contract flow. |
| **backend/app/p6_engine/comprehensive_validator.py** | Evidence phrase and WBS rule only; no extraction. |
| **backend/app/services/extraction/core/ontology.py** (line 116) | Token "temporary works" in an ontology list; not used to populate scope_items or obligation_entities in the current analyze_contract path. |

### PhraseExtractor / UnifiedExtractor / HybridAIExtractor

- **PhraseExtractor:** Not found as a top-level extractor in `analyze_contract`. Not in the call chain that fills `scope_items`.
- **UnifiedExtractor:** Called in `analyze_contract` as `extractor.extract(clean_text)` → `results_final`. `results_final` is used for dates, key_dates, clause summary, etc. **It is not used for scope_items.** `response_data["scope_items"]` is never set from `results_final`.
- **HybridAIExtractor:** When `enable_ai` is True, `scope_items = ai_struct.get("scope_items", [])` where `ai_struct = hybrid_extractor.extract_scope_constraints_milestones(clean_text)`. So **scope_items are the only source from contract analysis that feed obligations**, and they come **only** from the LLM response (JSON with key `"scope_items"`). The prompt does not explicitly require "Temporary Works"; inclusion is non-deterministic.

### Conclusion (contract analysis)

- "Temporary Works" is **not** deterministically extracted as an obligation entity or scope item. It appears only in regex/ontology support and in the validator’s evidence rule.
- **Scope items** (and thus the only path into obligation_entities from analysis) come **only** from **HybridAIExtractor**’s LLM output. There is no fallback list or phrase extractor that adds "Temporary Works" to scope_items.
- **mandatory_for_acceptance** is set at **obligation construction** time in `build_obligation_entities` (from scope classification or item flag), not at extraction time. If the item never reaches scope_items, it is never marked mandatory.

---

## 2. Obligation construction

- **File:** `backend/app/p6_engine/obligation_entities.py`, function **`build_obligation_entities(contract_data)`**.
- **Input:** `contract_data` must contain `scope_items`, `programme_compliance_model`, `constraints`, etc. `scope_items` are iterated (line 131); each item’s text is taken via `_original_text_from_item(item)` and added to `raw` with facet `FACET_SCOPE` and `mandatory` from the item or from `classify_scope_obligation(text)`.
- **No filter or reclassification** in this function removes or downgrades "Temporary Works". If "Temporary Works" were in `scope_items`, it would get signature `_obligation_signature("Temporary Works")` → `"temporary works"` (not in SIGNATURE_PHRASES; words → "temporary works") and would become one obligation with `mandatory_for_acceptance = True` (ACTION_REQUIRED).
- **Caller:** `build_frozen_requirements(response_data)` in `backend/app/p6_engine/frozen_requirements.py` calls `build_obligation_entities(contract_data)`. `response_data` is the analysis output; its `scope_items` are exactly those from HybridAIExtractor (see analyze_contract). So **if "Temporary Works" is not in `response_data["scope_items"]`, it is never passed to `build_obligation_entities` and never becomes an obligation.**

---

## 3. Validation input

- **File:** `backend/app/p6_engine/comprehensive_validator.py`, method **`validate()`** (around lines 924–931).
- **Check:** `obligation_entities = contract_data.get("obligation_entities") or {}` and `obligations_list = obligation_entities.get("obligations")`. So `contract_data["obligation_entities"]["obligations"]` is the list used for obligation mode.
- **Conclusion:** That list is produced only by `build_frozen_requirements` → `build_obligation_entities`. If "Temporary Works" was never added to scope_items and thus never turned into an obligation, **it is absent from `contract_data["obligation_entities"]["obligations"]` at the start of `validate()`.** It is not removed later; it was never present.

---

## 4. Validation processing

- **File:** `backend/app/p6_engine/comprehensive_validator.py`, **`_validate_obligation_entities()`**.
- **Input:** `obligations_list = entities.get("obligations") or []` (line 1945). Every obligation in that list is processed; results go into `obligations_report` (line 2151), and then into `scope_evidence_table` (lines 2357–2379) for obligations where `(r.get("facets") or {}).get("has_scope_component")` is True.
- **Conclusion:** If "Temporary Works" is not in `obligations_list`, it never appears in `obligations_report` or `scope_evidence_table`. There is no code path that removes it; it is missing because it was never in the input list.

---

## 5. Reporting layer

- **File:** `backend/app/reporting/validation_report_builder.py`, **`_section_scope_contract_alignment()`**.
- When `obligation_entities_used` is True, `scope_rows` and constraint rows are built from `scope_coverage["scope_evidence_table"]` and `scope_coverage["constraints_control"]`. Obligation lists (evidenced, not represented, etc.) come from `scope_coverage` (e.g. `obligations_evidenced`, `obligations_not_represented_but_mandatory`).
- **Conclusion:** No reporting filter hides obligations by type, facet, or evidence status. If an obligation is not in `scope_coverage` (because it was never in `obligations_list`), it cannot appear in the report.

---

## 6. Single root cause

**Temporary Works is missing because it is never added to `scope_items`.**

- `scope_items` in the analysis response are **only** taken from **HybridAIExtractor.extract_scope_constraints_milestones()** (when AI is enabled). There is no other source (UnifiedExtractor, PhraseExtractor, or a fixed list) that adds "Temporary Works".
- The LLM response does not guarantee that "Temporary Works" is included in `scope_items`. So it often never enters `contract_data["scope_items"]`, and therefore **never** reaches `build_obligation_entities`, `contract_data["obligation_entities"]["obligations"]`, `obligations_report`, or `scope_evidence_table`.

---

## 7. Minimum code change

**Goal:** Temporary Works is always included as a mandatory obligation, appears in scope & constraints, and blocks acceptability when not evidenced (with the existing WBS rule).

**Place:** `backend/app/p6_engine/obligation_entities.py`, function **`build_obligation_entities(contract_data)`**.

**Change:** After the existing loops that populate `raw` (from scope_items, PCM, constraints, governance), and **before** grouping by signature (before the line `by_signature: Dict[...] = {}`), **inject a single raw entry for "Temporary Works"** with facet SCOPE and mandatory True, **only if** no existing raw entry has signature equal to the one for "Temporary Works" (i.e. no text that normalizes to the same obligation as "Temporary Works").

- **Condition:** No `(text, ...)` in `raw` with `_obligation_signature(text) == _obligation_signature("Temporary Works")` (i.e. `"temporary works"`).
- **Action:** `add("Temporary Works", "", FACET_SCOPE, True, SCOPE_CLASSIFICATION_ACTION_REQUIRED)`.

**Effect:**

- "Temporary Works" is always present in `obligations` (as its own obligation or merged if the LLM already returned it).
- It has `has_scope_component` True and `mandatory_for_acceptance` True, so it appears in scope_evidence_table and in obligation lists, and blocks acceptability when not evidenced.
- The existing Temporary Works WBS rule in the validator continues to require ≥1 activity whose WBS path contains "Temporary Works" for that obligation to count as evidenced.

**Files and symbols:**

- **File:** `backend/app/p6_engine/obligation_entities.py`
- **Function:** `build_obligation_entities`
- **Constant:** `FACET_SCOPE` (already defined)
- **Constant:** `SCOPE_CLASSIFICATION_ACTION_REQUIRED` (already defined)
- **Helper:** `_obligation_signature("Temporary Works")` → `"temporary works"`
