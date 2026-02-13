# Acceptability Invariant

When **obligation_entities_used** is true, programme acceptability is determined **only** by obligation alignment.

## Rule

- **ACCEPTABLE** ⇔ every mandatory obligation is **aligned**.
- **aligned** ⇔ the obligation is satisfied according to its **evidence_mode** (evidenced by activities, or acknowledged, or an explicit assumption that counts for acceptability: client responsibility / out of scope at this stage).

## Single authority

- **Obligation alignment** is the only authority for acceptability when obligation entities are present.
- Nothing else may affect acceptability: no scores, confidence bands, scope summaries, programme compliance model (PCM), narrative text, or “professional judgement”.
- Assurance-based and “covered by later submission” are advisory only; they do **not** set aligned and do **not** make a programme ACCEPTABLE.

## Evidence modes

- **PHRASE**: phrase/component evidence (default).
- **WBS_ONLY**: evidence only if the obligation’s canonical match string appears in activity name or WBS path; no phrase or LLM evidence.
- **HYBRID**: phrase first; if not evidenced, then name/WBS substring match.

See `comprehensive_validator.py` and `validation_report_builder.py` for references to this invariant.

---

## Engine frozen

**The acceptability engine is frozen.** Future work must not modify acceptability logic without updating this document, the invariants in code, and the regression tests that protect the legal decision model.
