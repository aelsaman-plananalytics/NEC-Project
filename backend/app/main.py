"""
NEC Engineering Analysis System - FastAPI Application
Main entry point for the backend API.
"""

import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from app.routers import upload, analyze_contract, generate_report, validate_programme, full_review, auth, runs
from app.database import Base, engine
from app.models.user import User  # noqa: F401 - register model for create_all
from app.models.analysis_run import AnalysisRun  # noqa: F401 - register model for create_all
from app.runtime_paths import RUNTIME_DIR

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create output directories at startup (under project root / runtime)
OUTPUT_DIRS = [
    "analysis_reports",
    "validation_reports",
    "reports",
    "idempotency",
    "rate_limit",
    "submission_history",
    "acceptance_history",
    "contracts",
]

for folder in OUTPUT_DIRS:
    folder_path = RUNTIME_DIR / folder
    folder_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created/verified output directory: {folder_path}")

# Operational production readiness: config validation + integrity self-check (fail fast)
from app.startup_checks import run_config_validation, run_integrity_self_check
try:
    run_config_validation()
    run_integrity_self_check()
except RuntimeError as e:
    logger.critical(f"Startup failed: {e}")
    raise

logger.info("[OUTPUT DIRECTORIES READY]")
logger.info("[Runtime outputs → %s]", RUNTIME_DIR)
logger.info("[Analyze Contract → runtime/analysis_reports]")
logger.info("[Programme Validation → runtime/validation_reports]")
logger.info("[Report Generation → runtime/reports]")

# Get AI_MODE from environment
AI_MODE = os.getenv("AI_MODE", "mock").lower().strip()
if AI_MODE not in ["mock", "real", "azure"]:
    logger.warning(f"Invalid AI_MODE='{AI_MODE}'. Defaulting to 'mock'.")
    AI_MODE = "mock"

# Log AI_MODE on startup
logger.info("=" * 70)
logger.info("NEC Engineering Analysis System - Starting")
logger.info(f"AI_MODE: {AI_MODE.upper()}")
if AI_MODE == "mock":
    logger.info("  → Using MOCK engines (no OpenAI/Azure API required)")
    logger.info("  → RuleBasedMatcher + MockEmbeddingMatcher + MockLLMValidator")
elif AI_MODE == "azure":
    logger.info("  → Using AZURE OpenAI engines (requires AZURE_OPENAI_* env vars)")
    logger.info("  → RuleBasedMatcher + EmbeddingMatcher + LLMEngineeringValidator")
else:
    logger.info("  → Using REAL OpenAI engines (requires OPENAI_API_KEY)")
    logger.info("  → RuleBasedMatcher + EmbeddingMatcher + LLMEngineeringValidator")
logger.info("=" * 70)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: scheduler. Shutdown: stop scheduler and log."""
    try:
        from app.scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        logger.warning("[SCHEDULER] Startup failed: %s", e)
    yield
    try:
        from app.scheduler import shutdown_scheduler
        shutdown_scheduler()
    except Exception as e:
        logger.warning("[SHUTDOWN] Scheduler shutdown: %s", e)
    from datetime import datetime, timezone
    logger.info("[SHUTDOWN] NEC Engineering Analysis System shutting down at %s", datetime.now(timezone.utc).isoformat())


app = FastAPI(
    title="NEC Engineering Analysis System",
    description="Backend API for comparing NEC contracts against Primavera P6 programmes",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],  # Explicitly allow frontend origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security hardening: request size limit, rate limit, API key, audit log (API layer only)
from app.security_middleware import SecurityMiddleware
app.add_middleware(SecurityMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return a clear message when client sends JSON instead of multipart/form-data for file-upload endpoints."""
    from fastapi.responses import JSONResponse
    detail = exc.errors()  # method returning list of error dicts
    for err in detail:
        loc = err.get("loc") or ()
        msg = (err.get("msg") or "")
        if "body" in loc and "Expected UploadFile, received" in msg:
            return JSONResponse(
                status_code=400,
                content={
                    "error_code": "BAD_REQUEST",
                    "error_message": "This endpoint requires multipart/form-data with file uploads, not a JSON body.",
                    "details": "Send xer_file (required), and optionally previous_xer_file and json_file, as form file fields. Do not send application/json.",
                },
            )
    return JSONResponse(status_code=422, content={"detail": detail})

# Mount static files
static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Setup Jinja2 templates
templates_path = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_path))

# Create database tables (e.g. users) if they do not exist
Base.metadata.create_all(bind=engine)


# Include routers
app.include_router(auth.router)
app.include_router(runs.router)
app.include_router(upload.router)
app.include_router(analyze_contract.router)
app.include_router(generate_report.router)
app.include_router(validate_programme.router)
app.include_router(full_review.router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request):
    """Home page with links to upload forms."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Handle favicon requests to prevent 404 errors."""
    from fastapi.responses import Response
    return Response(status_code=204)  # No Content


@app.get("/health", tags=["system"])
async def health_check():
    """Legacy health check endpoint."""
    return {
        "status": "healthy",
        "service": "NEC Engineering Analysis System",
        "ai_mode": AI_MODE,
        "ai_mode_description": (
            "MOCK engines (no OpenAI)" if AI_MODE == "mock"
            else "AZURE OpenAI engines" if AI_MODE == "azure"
            else "REAL OpenAI engines"
        )
    }


@app.get("/api/v1/health", tags=["system"])
async def health_v1():
    """
    Operational health: integrity, ledger, storage, scheduler, database.
    Returns 500 with structured error if ledger verification fails.
    """
    from app.startup_checks import check_ledger_accessible
    from app.api_errors import structured_error_response, INTERNAL_ERROR

    payload = {
        "status": "healthy",
        "version": "v1",
        "integrity": "ok",
        "ledger_chain_check": "ok",
        "storage_check": "ok",
        "scheduler_running": False,
        "database_connected": False,
    }

    try:
        check_ledger_accessible()
    except RuntimeError as e:
        return structured_error_response(
            500,
            INTERNAL_ERROR,
            "Health check failed: ledger verification failed.",
            details=str(e),
        )

    # Database ping
    try:
        from app.database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            payload["database_connected"] = True
        finally:
            db.close()
    except Exception as e:
        payload["database_connected"] = False
        payload["database_error"] = str(e)

    # Storage write test (temporary file)
    try:
        from app.storage import get_storage
        import uuid
        test_path = f"_health_check_{uuid.uuid4().hex}.tmp"
        get_storage().save_bytes(test_path, b"health")
        if get_storage().exists(test_path):
            get_storage().delete(test_path)
        payload["storage_check"] = "ok"
    except Exception as e:
        payload["storage_check"] = "error"
        payload["storage_error"] = str(e)

    # Scheduler job status
    try:
        from app.scheduler import get_scheduler
        sched = get_scheduler()
        payload["scheduler_running"] = sched is not None and sched.running
    except Exception as e:
        payload["scheduler_error"] = str(e)

    return payload


@app.get("/api/ai_mode", tags=["system"])
async def get_ai_mode():
    """Get current AI_MODE configuration."""
    return {
        "ai_mode": AI_MODE,
        "description": (
            "MOCK engines (no OpenAI required)" if AI_MODE == "mock"
            else "AZURE OpenAI engines (requires AZURE_OPENAI_* env vars)" if AI_MODE == "azure"
            else "REAL OpenAI engines (requires OPENAI_API_KEY)"
        ),
        "engines": {
            "rule": "RuleBasedMatcher (always available)",
            "embedding": (
                "MockEmbeddingMatcher" if AI_MODE == "mock"
                else "EmbeddingMatcher (Azure OpenAI)" if AI_MODE == "azure"
                else "EmbeddingMatcher (OpenAI)"
            ),
            "llm": (
                "MockLLMValidator" if AI_MODE == "mock"
                else "LLMEngineeringValidator (Azure OpenAI)" if AI_MODE == "azure"
                else "LLMEngineeringValidator (OpenAI gpt-4o)"
            )
        }
    }


@app.options("/api/{path:path}", include_in_schema=False)
async def options_handler(path: str):
    """Handle CORS preflight requests."""
    from fastapi.responses import Response
    return Response(status_code=200)

