# Scope and Constraints — Single-Source-of-Truth Audit

## Invariant (enforced)

**When `obligation_entities_used == True`:**

- Scope and constraints reporting MUST:
  - be derived **only** from `obligation_entities` (e.g. `scope_evidence_table`, `constraints_control`);
  - **not** reference legacy `scope_items` or PCM for representation status;
  - **not** use implicit / assurance / confidence language from the legacy scope engine;
  - **not** run any legacy scope engine.

- Acceptability is determined **only** by the obligation-alignment oracle (mandatory obligations represented or not). The report must never say "Programme acceptable" while also saying "Scope item not represented" from a different (legacy) model.

---

## Ghost engines identified and gated

| Location | What it did | How it's gated |
|----------|-------------|-----------------|
| **comprehensive_validator.py** `_validate_scope_coverage` | Legacy scope: scope_items, PCM required_activities, phrase/semantic matching, COVERAGE_* labels | (1) Never called when `has_obligation_entities` (call site branches to `_validate_obligation_entities` only). (2) **Tripwire added**: at entry, if `contract_data["obligation_entities"]["obligations"]` is non-empty, raises `RuntimeError` ("Ghost engine: _validate_scope_coverage must not run when contract has obligation_entities"). |
| **validation_report_builder.py** `_section_scope_contract_alignment` legacy path | Built scope_rows from scope_items, matched_map/missing_map, _classify_scope_item, COVERAGE_EXPLICIT/IMPLICIT/ASSURANCE/NONE, activity_load, constraint_rows from constraint phrase matching | Runs **only** when `obligation_entities_used` is falsy. When `obligation_entities_used` is True, only the obligation branch runs (scope_evidence_table + constraints_control); legacy loop and legacy constraint logic are in the `else` and are not executed. |

No legacy scope engine runs in obligation mode.

---

## Functions modified (none deleted)

- **validation_report_builder.py** `_section_scope_contract_alignment`  
  - **Obligation branch:** Builds `scope_rows` only from `scope_coverage["scope_evidence_table"]`, `constraint_rows` only from `scope_coverage["constraints_control"]`; sets `scope_summary` and `constraint_summary` with obligation-only messaging.  
  - **Legacy branch:** Entire legacy logic (scope_items loop, activity_load, scope_counts, scope_summary, constraint_rows from constraints, constraint_summary) moved into the `else` block and correctly indented; loop body indentation fixed.  
  - **Invariant:** Docstring and comments document that when `obligation_entities_used`, scope/constraints come only from obligation alignment.

- **comprehensive_validator.py** `_validate_scope_coverage`  
  - **Tripwire:** At start of function, if `contract_data` has non-empty `obligation_entities["obligations"]`, raises `RuntimeError` so this path never runs in obligation mode.

- **validate_programme.py** (already done in prior work)  
  - Removed the second call that overwrote `validation_output["validation_summary"]` with `_calculate_validation_summary(validation_output)`; validation_summary is set only inside `validator.validate()`.

---

## Where `obligation_entities_used` is enforced

| File | Enforcement |
|------|-------------|
| **comprehensive_validator.py** | (1) Scope source: if `has_obligation_entities` → only `_validate_obligation_entities` sets `alignment["scope_coverage"]`; `_validate_scope_coverage` not called. (2) Tripwire inside `_validate_scope_coverage` raises if obligation_entities present. (3) PCM/required_activities guards; acceptability and failure reasons from single oracle when `obligation_entities_used`; executive summary and missing lists from obligation data only. |
| **validation_report_builder.py** | `_section_scope_contract_alignment`: if `obligation_entities_used` → obligation-only branch (scope_evidence_table, constraints_control, obligation-only summaries); else → legacy branch. Tripwire: cannot output "acceptable" while `acceptability_failure_reasons` non-empty; cannot output "acceptable" while `obligations_not_represented_but_mandatory` non-empty when obligation_entities_used. |

---

## Confirmation: scope & constraints cannot contradict acceptability

- **Acceptability** comes from a single place when `obligation_entities_used`: the validator’s acceptability oracle (mandatory obligations represented or not). It is stored in `validation_summary` and not recalculated in the report builder.
- **Scope/constraints section** in obligation mode is built only from `scope_evidence_table` and `constraints_control`, which are the same obligation-alignment outputs that drive acceptability. So the narrative (e.g. "Explicit in programme", "Not represented", etc.) is the same source of truth as acceptability.
- **Tripwires:** (1) Report builder raises if it would output "acceptable" while `acceptability_failure_reasons` is non-empty. (2) Report builder raises if it would output "acceptable" while `obligations_not_represented_but_mandatory` is non-empty when obligation_entities_used. (3) Validator raises if `_validate_scope_coverage` is ever invoked with obligation_entities present.

Result: the system does not report "Programme acceptable" alongside a legacy "Scope item not represented" from a different model; scope/constraints and acceptability are aligned to the single obligation-alignment authority.
