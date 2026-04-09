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

## More detailed docs

- Backend run guide: `backend/docs/RUN_INSTRUCTIONS.md`
- Frontend readme: `frontend/README.md`

