# API Response Contract: /api/validate_programme

This document defines the **product API boundary** for programme validation. Acceptability is determined only by obligation alignment; see [ACCEPTABILITY_INVARIANT.md](ACCEPTABILITY_INVARIANT.md).

## Authoritative fields (decision-making, legally binding)

These fields are set **only** by the validator. The router **must not** infer or recompute them. No confidence, narrative, or advisory data may affect them.

| Field | Type | Description |
|-------|------|-------------|
| `acceptability_status` | `"ACCEPTABLE"` \| `"NOT_ACCEPTABLE"` | Legal acceptability: every mandatory obligation aligned ⇔ ACCEPTABLE |
| `overall_status` | `"pass"` \| `"fail"` \| ... | Derived from acceptability (pass ⇔ no mandatory unaligned) |
| `submission_stage` | `"initial"` \| `"interim"` \| `"final"` \| `null` | Echo of request; does not change acceptability |
| `obligations_report` | array | Per-obligation alignment from validator |
| `obligations_not_represented_but_mandatory` | array | Mandatory obligations not evidenced (empty when ACCEPTABLE) |
| `scope_evidence_table` | array | Scope evidence rows from validator |

## Planner / lifecycle guidance (non-authoritative)

These fields are for workflow and visibility only. They **must never** override evidence or acceptability. `covered_by_later_submission` does **not** satisfy WBS_ONLY obligations.

| Field | Type | Description |
|-------|------|-------------|
| `lifecycle_expectations` | string | Maturity text for the submission stage |
| `obligation_readiness` | array | `{ obligation_id, required_now, aligned, required_action }` per obligation |
| `planner_assumptions_used` | array | Echo of planner-declared assumptions |

## Invariants

- If `acceptability_status === "ACCEPTABLE"` then `obligations_not_represented_but_mandatory` is empty.
- WBS_ONLY obligations cannot be satisfied by assumptions; they require programme evidence (WBS/activity).
- Implementation: [app/api_contract.py](app/api_contract.py); router: [app/routers/validate_programme.py](app/routers/validate_programme.py).
