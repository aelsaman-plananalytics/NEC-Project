# Outputs

This directory contains generated analysis and validation reports.

## Folders

### `analysis_reports/`

JSON files from **contract analysis** (`/api/analyze_contract`).

**Naming:** `analysis_{contract_name}_{timestamp}.json`

**Example:** `analysis_Contract_Data_Parts_1_and_2_20241204_143022.json`

**Contents:** Contract text, scope_items, admin_items, drawing_references, summary, metadata.

---

### `validation_reports/`

JSON files from **programme validation** (`/api/validate_programme`). Each run saves the full validation output here.

**Naming:** `validation_{timestamp}.json` (e.g. `validation_20260129_104758.json`)

**Contents:** contract_summary, programme_summary, alignment, nec_alignment_detailed, programme_kpis, schedule_health, logic_checks, risks, recommendations, validation_summary, ai_review, metadata (including `output_path` and `output_filename`).

**Notes:** The API response includes `metadata.output_path` and `metadata.output_filename` so you know exactly where the file was saved.

---

### `reports/`

Generated PDF/DOCX/HTML reports (e.g. from `/api/generate_report`).

## General

- Files are generated automatically on each analysis or validation run.
- Old files are not automatically deleted (manage manually if needed).
- Output files are excluded from git via `.gitignore`.



