# NEC Engineering Analysis Frontend

React frontend for the NEC Engineering Analysis System.

## Setup

### Prerequisites

- Install **Node.js LTS** (includes `node` + `npm`).
- Verify in a new terminal:

```bash
node -v
npm -v
```

1. Install dependencies:
```bash
npm install
```

2. Create a `.env` file in the frontend directory (optional):
```
REACT_APP_API_URL=http://localhost:8000
```

3. Start the development server:
```bash
npm start
```

The app will open at http://localhost:3000

## Features

- Contract Analysis page with drag & drop file upload
- Feature extraction visualization
- JSON viewer for full API responses

## API Configuration

By default, the frontend connects to `http://localhost:8000`. 
To change this, set the `REACT_APP_API_URL` environment variable.

## Troubleshooting

### `npm` / `node` is not recognized (Windows)

Cause: Node.js is not installed or not on PATH.

Fix:
- Install **Node.js LTS**
- Close/reopen terminals (PATH refresh)
- Re-run:

```powershell
where.exe node
where.exe npm
node -v
npm -v
```

### Backend not reachable

- Ensure backend is running: `http://localhost:8000/health`
- If API is on a different host/port, set `REACT_APP_API_URL` in `frontend/.env`.


