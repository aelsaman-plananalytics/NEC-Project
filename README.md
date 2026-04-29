# NEC Engineering Analysis System

This repo contains a **FastAPI backend** and a **React frontend**.

## Quick start (dev)

### Backend (API)

1. Create a project root `.env` file at `./.env`.

At minimum, this is enough to boot in mock mode (no OpenAI/Azure calls):

```env
AI_MODE=mock
DATABASE_URL=postgresql://user:password@localhost:5432/nec_db
JWT_SECRET_KEY=change-me-in-production
```

For the full list (Azure/OpenAI options, Supabase notes, etc.), see `backend/docs/RUN_INSTRUCTIONS.md`.

2. Start the backend:

```bash
cd backend
..\venv\Scripts\Activate.ps1  # PowerShell (Windows) - optional if already activated
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3. Verify:

- `http://localhost:8000/health`
- `http://localhost:8000/docs`

### Frontend (React)

1. Install and run:

```bash
cd frontend
npm install
npm start
```

2. Open:

- `http://localhost:3000`

By default, the frontend points at `http://localhost:8000`. To override, create `frontend/.env`:

```env
REACT_APP_API_URL=http://localhost:8000
```

## Testing (backend)

From the `backend` directory:

```bash
..\venv\Scripts\Activate.ps1  # PowerShell (Windows)
python -m pytest -q
```

## Troubleshooting (if this happens again)

### 1) `Fatal error in launcher ... venv\\Scripts\\python.exe ... The system cannot find the file specified`

Cause: the `venv/` was created on a different machine/user and contains hardcoded paths (e.g. `C:\\Users\\someone_else\\...`).

Fix (Windows PowerShell, repo root):

```powershell
Remove-Item -Recurse -Force .\\venv
python -m venv .\\venv
& .\\venv\\Scripts\\python.exe -m pip install -r backend\\requirements.txt
& .\\venv\\Scripts\\python.exe -m pip install pytest
```

### 2) `npm` / `node` is not recognized

Cause: Node.js is not installed or not on PATH.

Fix:
- Install **Node.js LTS** (includes `node` and `npm`)
- Close and reopen terminals (PATH refresh)
- Verify:

```powershell
node -v
npm -v
```

### 3) `pydantic ValidationError ... AI_MODE Extra inputs are not permitted`

Cause: `AI_MODE` is set in `.env` but the backend settings model may not accept it, depending on branch/version.

Checks:
- Open `./.env` and verify `AI_MODE` is one of: `mock`, `real`, `azure`
- If tests fail at import time due to settings, temporarily set `AI_MODE=mock` and re-run.

### 4) Stage-based acceptability looks “wrong”

If acceptability thresholds depend on `submission_stage`, ensure the request is passing a real stage value:
- The API expects a stage like `initial`, `revised`, or `final` (lowercase).
- If your client is sending `"string"` (placeholder), it will be treated as `initial`.

## Safety notes

- **Do not commit** `.env` files or API keys.

## More detailed docs

- Backend run guide: `backend/docs/RUN_INSTRUCTIONS.md`
- Frontend readme: `frontend/README.md`
- If decisions go wrong again: `backend/docs/IN_CASE_DECISION_GOES_WRONG_AGAIN.md`

