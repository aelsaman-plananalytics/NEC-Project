# NEC Project — Documentation

This folder contains the main documentation for the NEC Engineering Analysis System.

## Index

| Document | Description |
|----------|-------------|
| [RUN_INSTRUCTIONS.md](RUN_INSTRUCTIONS.md) | How to run the system: backend and frontend setup, prerequisites, and run steps. |
| [TESTING_BACKEND_E2E.md](TESTING_BACKEND_E2E.md) | E2E testing: upload contract + programme, get PDF report (full_review, curl, script). |
| [ACCEPTABILITY_INVARIANT.md](ACCEPTABILITY_INVARIANT.md) | Acceptability rules: single authority, evidence modes, and obligation alignment. |
| [API_RESPONSE_CONTRACT.md](API_RESPONSE_CONTRACT.md) | Product API boundary for `/api/validate_programme`: authoritative vs guidance fields. |
| [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md) | Summary of refactoring and structural changes. |
| [SCOPE_CONSTRAINTS_AUDIT.md](SCOPE_CONSTRAINTS_AUDIT.md) | Audit of scope and constraints handling. |
| [SINGLE_SOURCE_OF_TRUTH_AUDIT.md](SINGLE_SOURCE_OF_TRUTH_AUDIT.md) | Audit of single source of truth for validation and reporting. |
| [TEMPORARY_WORKS_TRACE.md](TEMPORARY_WORKS_TRACE.md) | Trace of Temporary Works obligation behaviour. |
| [TEMPORARY_WORKS_DEBUG_TRACE.md](TEMPORARY_WORKS_DEBUG_TRACE.md) | Debug trace for Temporary Works. |

## Quick commands (Windows / PowerShell)

From `NEC-Project/backend`:

```powershell
& ..\\venv\\Scripts\\Activate.ps1
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run tests:

```powershell
& ..\\venv\\Scripts\\Activate.ps1
python -m pytest -q
```

## Troubleshooting notes

- **Broken venv launcher** (`Fatal error in launcher ... system cannot find the file specified`):
  - Recreate the venv from the repo root. See root `README.md` → Troubleshooting.
- **Settings import fails on `AI_MODE`**:
  - If you see `ValidationError: AI_MODE Extra inputs are not permitted`, set `AI_MODE=mock` in `NEC-Project/.env` (or update the settings model to accept it, depending on your branch).
- **Frontend build tooling missing**:
  - `npm`/`node` not found means Node.js LTS is not installed or not on PATH. See `frontend/README.md`.

## Other documentation

- **Frontend:** [../frontend/README.md](../frontend/README.md)
- **Backend outputs:** [../backend/README.md](../backend/README.md)
- **If decisions go wrong again:** [./docs/IN_CASE_DECISION_GOES_WRONG_AGAIN.md](./docs/IN_CASE_DECISION_GOES_WRONG_AGAIN.md)
