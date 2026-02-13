# Single Source of Truth — Execution Graph and Ghost-Path Audit

## System invariant (non-negotiable)

When `obligation_entities_used == True`:

- **Acceptability** comes ONLY from obligation alignment (mandatory obligations evidenced/explicit_assumption or not).
- **Scope & constraints reporting** comes ONLY from obligation alignment (`scope_evidence_table`, `constraints_control`).
- Legacy `scope_items` / PCM / implicit / assurance / confidence logic MUST NOT RUN.
- The report must NEVER show "acceptable" alongside any unrepresented mandatory obligation.

---

## 1. Execution graph: `/api/validate_programme` → `validator.validate()`

### Call chain

| Step | Function / location | Reads acceptability? | Writes acceptability? | Builds scope/constraint rows? | Can run when obligation_entities_used? |
|------|---------------------|----------------------|------------------------|-------------------------------|----------------------------------------|
| 1 | `validate_programme` (router) | — | No | No | — |
| 2 | `_run_programme_validation` | — | No | No | — |
| 3 | `ComprehensiveValidator().validate()` | — | No (delegates) | No | — |
| 4 | `_extract_contract_clauses` | No | No | No | Yes (data only) |
| 5 | `_extract_programme_data` | No | No | No | Yes |
| 6 | `_perform_nec_alignment_with_summary` | No | No | No | Yes |
| 7a | `_validate_obligation_entities` (when has_obligation_entities) | No | Yes (sets scope_coverage; drives acceptability) | Yes (scope_evidence_table, constraints_control) | **Only** when obligation_entities_used |
| 7b | `_validate_scope_coverage` (else) | No | Yes (sets scope_coverage) | Yes (legacy scope_items) | **No** — gated by branch + tripwire |
| 8 | `_calculate_validation_summary` | Yes (scope_coverage) | **Yes** (acceptability_status, overall_status) | No | Yes; when obligation_entities_used it reads only scope_coverage (obligation oracle) |
| 9 | Post-validate in router: `validation_output["logic_checks"]`, `["schedule_health"]`, `["alignment"] = pop("nec_alignment")`, `["programme_summary"]["circular_dependencies"]` | No | **No** (does not write validation_summary or scope_coverage) | No | — |
| 10 | `review_validation` (AI) | Reads validation_summary | **No** (returns separate dict) | No | — |
| 11 | `build_validation_report` (when report is generated) | Yes (validation_summary, scope_coverage) | No | Yes (`_section_scope_contract_alignment`) | Yes; scope section gated by obligation_entities_used |

### Critical write points for acceptability

- **`_calculate_validation_summary`** (comprehensive_validator.py): Only place that sets `acceptability_status` and `overall_status`. When `obligation_entities_used`, it uses only `scope_coverage["acceptability_failure_reasons"]` and `obligations_not_represented_but_mandatory`; it does not use PCM or legacy scope_items_missing for acceptability.
- **`_validate_obligation_entities`**: Populates `scope_coverage` (including `acceptability_failure_reasons`, `obligations_not_represented_but_mandatory`) that `_calculate_validation_summary` reads. Does not set validation_summary directly.

### Critical build of scope/constraint rows

- **Obligation path:** `_section_scope_contract_alignment` (report builder) when `obligation_entities_used`: builds `scope_rows` only from `scope_evidence_table`, `constraint_rows` only from `constraints_control`. No legacy COVERAGE_* or scope_items.
- **Legacy path:** Same function in `else`: builds from `scope_items`, PCM, `_classify_scope_item`, COVERAGE_*, constraint phrase matching. Runs only when `obligation_entities_used` is falsy.

---

## 2. Ghost writers — search results and status

| Search term | Where it appears | Can run when obligation_entities_used? | Status |
|-------------|------------------|----------------------------------------|--------|
| **"acceptable"** | validation_report_builder: acceptability_clarification "acceptable at this stage" | Yes, but text is only set from validation_summary; no independent calculation | OK — mirrors validator |
| **"Acceptable at this stage"** | comprehensive_validator: programme_decision_text | Yes — set inside _calculate_validation_summary when acceptability_status == ACCEPTABLE | OK — single writer |
| **scope_items** | Report builder: only in `else` (legacy) branch | **No** — branch not taken when obligation_entities_used | Gated |
| **_classify_scope_item** | Report builder: only in legacy loop | **No** | Gated |
| **COVERAGE_** (Explicit/Implicit/Assurance/None) | Report builder: only in legacy branch | **No** | Gated |
| **Implicitly represented / Assurance-based** | Report builder: legacy row_status; validator: labels for obligation types | Obligation path uses representation_status_label from validator (Evidenced, Explicit assumption, Not represented but mandatory, etc.) — not COVERAGE_IMPLICIT/ASSURANCE | OK — obligation path does not use these legacy labels |
| **confidence** | Report builder: obligation branch uses "From obligation alignment"; legacy uses CONFIDENCE_* | Obligation path does not use legacy confidence bands | Gated |
| **programme aligns** | Report builder: acceptability_clarification when ACCEPTABLE | Only when vs says ACCEPTABLE; tripwires prevent ACCEPTABLE when not_rep | OK |
| **scope_summary** / **constraint_summary** | Set in both branches; obligation branch sets obligation-only text | No leak — each branch sets its own | OK |

**Conclusion:** No ghost writer runs in obligation mode. Legacy scope/constraint building and legacy labels run only in the `else` branch when `obligation_entities_used` is false.

---

## 3. Runtime branching verification

### `_section_scope_contract_alignment` (validation_report_builder.py)

- **Before branch:** `scope_rows`, `constraint_rows` = [], `scope_summary` = "", `activity_load_notes` = [].
- **if obligation_entities_used:** Fills scope_rows from scope_evidence_table, constraint_rows from constraints_control, sets scope_summary and constraint_summary. No reference to scope_items, PCM, matched_map, COVERAGE_*, or _classify_scope_item.
- **else:** Uses scope_items, PCM, matched_map, missing_map, _classify_scope_item, COVERAGE_*, activity_load, constraint_rows from constraints list. All of this is inside the same `else`; no shared mutation with the obligation branch.
- **After branch:** `constraint_summary` is set in both branches (obligation branch always sets it; legacy branch sets it in the else). No default from legacy leaks into obligation path.

### `_perform_nec_alignment_with_summary` (comprehensive_validator.py)

- **if has_obligation_entities:** Calls only `_validate_obligation_entities`; `_validate_scope_coverage` is not called.
- **else if frozen_primary_used:** Calls `_validate_against_frozen_requirements`.
- **else:** Calls `_validate_scope_coverage`. Tripwire at entry of `_validate_scope_coverage` raises if contract has non-empty obligation_entities.

### `_calculate_validation_summary` (comprehensive_validator.py)

- **if obligation_entities_used:** tier1 does not add scope_coverage from scope_items_missing (lines 3076–3081 skip that block). failure_reasons = scope_cov.get("acceptability_failure_reasons"). acceptability from hard_breaches (from explicit_failures). overall_status = pass iff not failure_reasons; tripwires if pass but failure_reasons or obligations_not_represented_but_mandatory.
- **else:** Legacy path uses PCM, scope_coverage.status, scope_items_missing, etc.

No shared variables are mutated before the branch in a way that would let legacy logic affect obligation mode.

---

## 4. Post-validation mutation check

- **Router** (`validate_programme.py`): Adds `logic_checks`, `schedule_health`, renames `nec_alignment` → `alignment`, adds `programme_summary["circular_dependencies"]`. Does **not** modify `validation_summary`, `scope_coverage`, or `obligations_report`.
- **AI review** (`review_validation`): Receives validation_summary and alignment; returns a separate dict (`confirmed`, `corrections`, `notes`). Does **not** mutate validation_output or validation_summary.
- **Report generator**: Calls `build_validation_report(data)` with the same data; report builder only reads and builds sections. Does not mutate validation_output.

**Conclusion:** No illegal post-validation mutation of validation_summary, scope_coverage, or obligations_report.

---

## 5. UI / API layer

- **ValidationReview.jsx:** Uses `section_scope_contract_alignment.scope_rows` and `validation_summary.acceptability_status` from API/report. Does not reconstruct scope from raw scope_items.
- **ProgrammeCompare.jsx:** Uses `vs.acceptability_status` from API.
- **ContractAnalysis.jsx:** Uses `scope_items` from **analyze_contract** output (different flow), not from validation report.
- **Report generator (PDF/Word/HTML):** Uses `scope_sec.scope_summary`, `scope_sec.constraint_summary`, `scope_sec.scope_rows` from `build_validation_report` output. No mixing of legacy scope_items with obligation summaries; report builder is the single producer of scope_sec.

**Conclusion:** UI and report outputs render only what the API/report builder sends; no reconstruction of scope/constraints from raw scope_items in the validation path.

---

## 6. Hard-fail tripwires (implemented)

| Tripwire | Location | Condition | Action |
|----------|----------|-----------|--------|
| Legacy scope engine must not run with obligation_entities | comprehensive_validator.py `_validate_scope_coverage` | `obligation_entities["obligations"]` non-empty | Raise RuntimeError ("Ghost engine: _validate_scope_coverage must not run when contract has obligation_entities") |
| Acceptable while failure reasons | validation_report_builder.py `_section_scope_contract_alignment` | acceptability_status == ACCEPTABLE and acceptability_failure_reasons non-empty | Raise RuntimeError; refuse to generate report |
| Acceptable while mandatory not represented | validation_report_builder.py `_section_scope_contract_alignment` | acceptability_status == ACCEPTABLE and obligation_entities_used and obligations_not_represented_but_mandatory non-empty | Raise RuntimeError |
| Scope row "Not represented but mandatory" while ACCEPTABLE | validation_report_builder.py `_section_scope_contract_alignment` | obligation_entities_used and ACCEPTABLE and any scope_row.representation_status == "Not represented but mandatory" | Raise RuntimeError |
| Pass with unaligned obligations | validation_report_builder.py `build_validation_report` | overall_status == "pass" and obligation_entities_used and any mandatory not aligned | Raise RuntimeError |
| Pass with only covered_by_later_submission for mandatory | validation_report_builder.py `build_validation_report` | pass and mandatory has only covered_by_later_submission | Raise RuntimeError |
| Acceptability contradiction in validator | comprehensive_validator.py `_calculate_validation_summary` | ACCEPTABLE and obligations_not_represented_but_mandatory non-empty | Raise RuntimeError |
| overall_status = pass but failure_reasons non-empty | comprehensive_validator.py `_calculate_validation_summary` | obligation_driven_status and pass and failure_reasons | Raise RuntimeError |
| validate() final invariant | comprehensive_validator.py `validate()` | obligation_entities_used and any mandatory not aligned | Raise RuntimeError |

---

## 7. Summary: ghost paths and fixes

### Ghost paths found

1. **Legacy scope engine** (`_validate_scope_coverage`): Cannot run when obligation_entities present — call site branches to `_validate_obligation_entities` only; plus **tripwire at entry** raises if called with obligation_entities. **Status:** Guarded.
2. **Legacy scope/constraint section in report** (`_section_scope_contract_alignment` else branch): Builds scope_rows from scope_items, COVERAGE_*, _classify_scope_item. **Status:** Runs only when `obligation_entities_used` is false; obligation branch is isolated and uses only scope_evidence_table and constraints_control.
3. **_calculate_validation_summary** reading legacy scope_items_missing: When `obligation_entities_used`, the block that adds scope_coverage.status/fail or scope_items_missing to tier1 is skipped (line 3076: `if ... and not obligation_entities_used`). **Status:** No ghost.

### What would explain “acceptable” + “scope not represented” (if it had occurred)

- If the **report** ever showed “Programme acceptable” and a scope row “Not represented” for a **mandatory** obligation, the cause would be either:
  - **Data:** acceptability_status set to ACCEPTABLE while obligations_not_represented_but_mandatory was non-empty (validator/report tripwires now prevent this), or
  - **Report building:** scope_rows in obligation mode containing a row with "Not represented but mandatory" while status is ACCEPTABLE (new tripwire raises in that case).

### Exact code changes made in this audit

1. **validation_report_builder.py**
   - Added tripwire: when `obligation_entities_used` and `acceptability_status == "ACCEPTABLE"`, if any `scope_row.representation_status == "Not represented but mandatory"` → raise RuntimeError (scope and acceptability must not contradict).

2. **comprehensive_validator.py**
   - (Already present) Tripwire at start of `_validate_scope_coverage`: if contract has non-empty `obligation_entities["obligations"]` → raise RuntimeError.

3. **No deletions.** Legacy path retained for non-obligation contracts; fully isolated in `else` and never runs when `obligation_entities_used`.

### Confirmation: system behaviour

- **FAIL loudly:** If mandatory obligations are not aligned or data is inconsistent, RuntimeError is raised in validator or report builder; no report is generated with a contradiction.
- **PASS cleanly:** When all mandatory obligations are aligned and no contradiction exists, acceptability is ACCEPTABLE and scope/constraints section shows only obligation-derived content; no legacy scope_items or COVERAGE_* in that mode.
- **NEVER contradict:** Tripwires ensure we never output "acceptable" while failure_reasons exist, or while obligations_not_represented_but_mandatory is non-empty, or while a scope row shows "Not represented but mandatory" in obligation mode.

Single source of truth: when `obligation_entities_used == True`, acceptability and scope/constraints reporting are derived only from obligation alignment; legacy scope engines do not run and cannot overwrite or contradict.
