# How to Run the NEC Engineering Analysis System

This guide will help you set up and run both the backend and frontend of the application.

## Prerequisites

- Python 3.9+ installed
- Node.js 16+ and npm installed (for frontend)
- PostgreSQL database (if using database features)
- PyMuPDF, Tesseract OCR, and other dependencies (see installation steps)

## Step 1: Backend Setup

### 1.1 Activate Virtual Environment

If you haven't already, activate your virtual environment:

**Windows:**
```powershell
cd backend
.\venv\Scripts\Activate.ps1
```

**Linux/Mac:**
```bash
cd backend
source venv/bin/activate
```

### 1.2 Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

**Note:** Some dependencies may require additional system libraries:
- **PyMuPDF**: Should install automatically via pip
- **Camelot**: Requires `ghostscript` and `tcl-tk` (see [Camelot installation guide](https://camelot-py.readthedocs.io/en/master/user/install.html))
- **Tesseract OCR**: Requires Tesseract to be installed on your system:
  - Windows: Download from [GitHub](https://github.com/UB-Mannheim/tesseract/wiki)
  - Linux: `sudo apt-get install tesseract-ocr`
  - Mac: `brew install tesseract`

### 1.3 Create Environment File

Create a `.env` file in the **project root** (`NEC-Project/.env`). The backend reads from there (it also checks `backend/.env` if you ever add one).

```env
# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/nec_db

# AI Mode: "mock", "real", or "azure"
AI_MODE=mock

# Azure OpenAI Configuration (required if AI_MODE=azure)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-azure-api-key
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment-name
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# OpenAI Configuration (required if AI_MODE=real)
OPENAI_API_KEY=your-openai-api-key

# Optional: Debug mode
DEBUG=False

# Auth (production): set a strong secret for JWT signing
JWT_SECRET_KEY=your-secret-key-change-in-production

# Optional: email verification at signup (ZeroBounce). If set, only deliverable emails can register.
# Get an API key at https://www.zerobounce.net/ (free tier available). Leave empty to skip verification.
# EMAIL_VERIFICATION_API_KEY=your-zerobounce-api-key
```

**Auth and database:** The app uses PostgreSQL for user accounts. On startup it creates the `users` table if it does not exist. Sign up and login are stored in the database; the frontend receives a JWT and sends it with API requests. For production, set `JWT_SECRET_KEY` in `.env` to a long random string. Optionally set `EMAIL_VERIFICATION_API_KEY` (ZeroBounce) to verify that signup emails are deliverable; if unset, only format validation is used.

**Existing databases:** If you already have a `users` table and see errors like `column users.organisation_logo_url does not exist`, add the new columns by running the migration from the `backend` directory:
```bash
# Replace with your DB user and database name (from DATABASE_URL)
psql -U your_user -d nec_db -f migrations/add_user_settings_columns.sql
```
Or run in a PostgreSQL client (e.g. pgAdmin, psql):
```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS report_naming_preference VARCHAR(64) NOT NULL DEFAULT 'contract_date_validation';
ALTER TABLE users ADD COLUMN IF NOT EXISTS data_retention_days INTEGER NOT NULL DEFAULT 365;
ALTER TABLE users ADD COLUMN IF NOT EXISTS organisation_logo_url VARCHAR(512);
ALTER TABLE users ADD COLUMN IF NOT EXISTS preferences JSONB;
```

**Using Supabase:** To use a Supabase project as the database:
1. Wait for the project to finish setting up (dashboard shows "Active").
2. In Supabase: **Project Settings** (gear icon) → **Database**.
3. Under **Connection string**, choose **URI** and copy the connection string (use **Transaction** mode, port 6543, for connection pooling).
4. Replace `[YOUR-PASSWORD]` in the string with your database password (the one you set when creating the project; you can reset it under Database → Database password).
5. Put the full URI in your project root `.env` as `DATABASE_URL=postgresql://...`. The app adds `?sslmode=require` if needed.
6. Start the backend; it will create the `users` and `analysis_runs` tables automatically on first run.

The **Project URL** and **API keys** in the Supabase dashboard are for Supabase’s client APIs. This backend connects with the **PostgreSQL connection string** only; no Supabase API key is required in `.env`.

**For testing without AI features**, you can use:
```env
AI_MODE=mock
DATABASE_URL=postgresql://user:password@localhost:5432/nec_db
```

### 1.4 Run the Backend Server

From the `backend` directory:

```bash
# Using uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using Python module syntax
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend will start on `http://localhost:8000`

**Verify it's running:**
- Open `http://localhost:8000/health` in your browser
- You should see a JSON response with status "healthy"

**API Documentation:**
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Step 2: Frontend Setup (Optional)

If you want to run the React frontend:

### 2.1 Install Frontend Dependencies

```bash
cd frontend
npm install
```

### 2.2 Run the Frontend

```bash
npm start
```

The frontend will start on `http://localhost:3000` and automatically open in your browser.

## Step 3: Test the Application

### Test Backend Endpoints

1. **Health Check:**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Upload and Analyze Contract:**
   ```bash
   curl -X POST "http://localhost:8000/api/analyze-contract" \
     -H "accept: application/json" \
     -F "file=@path/to/your/contract.pdf"
   ```

### Using the Web Interface

1. Open `http://localhost:8000` in your browser
2. Use the upload forms to test PDF contract analysis

## Common Issues and Solutions

### Issue: "PyMuPDF not available"
**Solution:** Install PyMuPDF:
```bash
pip install PyMuPDF
```

### Issue: "Camelot extraction failed"
**Solution:** Install system dependencies for Camelot:
- Windows: Install Ghostscript from [official site](https://www.ghostscript.com/download/gsdnld.html)
- Linux: `sudo apt-get install ghostscript python3-tk`
- Mac: `brew install ghostscript`

### Issue: "Tesseract not found"
**Solution:** Install Tesseract OCR on your system (see Prerequisites section)

### Issue: "ModuleNotFoundError: No module named 'app'"
**Solution:** Make sure you're running from the `backend` directory or set PYTHONPATH:
```bash
# Windows PowerShell
$env:PYTHONPATH = "$PWD"
# Or run from backend directory
cd backend
python -m uvicorn app.main:app --reload
```

### Issue: Database connection errors
**Solution:** 
- Ensure PostgreSQL is running
- Check your `DATABASE_URL` in `.env` file
- Some features may work without a database if you're only using contract analysis

## Development Mode

For development with auto-reload:

```bash
# Backend (auto-reloads on code changes)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (auto-reloads on code changes)
cd frontend
npm start
```

## Production Deployment

For production, use a production ASGI server like:

```bash
# Using gunicorn with uvicorn workers
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Quick Start (Minimal Setup)

If you just want to test the contract analysis without database:

1. **Create minimal `.env`:**
   ```env
   AI_MODE=mock
   DATABASE_URL=postgresql://user:pass@localhost/db
   ```

2. **Start backend:**
   ```bash
   cd backend
   .\venv\Scripts\Activate.ps1  # Windows
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

3. **Test:**
   - Visit `http://localhost:8000/health`
   - Visit `http://localhost:8000/docs` for API documentation

## Next Steps

- Upload a PDF contract via the web interface or API
- Check the `/backend/app/outputs/` directory for analysis results
- Review the API documentation at `/docs` endpoint
