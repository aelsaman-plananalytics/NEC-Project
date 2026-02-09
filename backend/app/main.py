"""
NEC Engineering Analysis System - FastAPI Application
Main entry point for the backend API.
"""

import os
import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from app.routers import upload, analyze_contract, generate_report, validate_programme, full_review, auth, runs
from app.database import Base, engine
from app.models.user import User  # noqa: F401 - register model for create_all
from app.models.analysis_run import AnalysisRun  # noqa: F401 - register model for create_all

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create output directories at startup
OUTPUT_DIRS = [
    "app/outputs/analysis_reports",
    "app/outputs/validation_reports",
    "app/outputs/reports"
]

for folder in OUTPUT_DIRS:
    folder_path = Path(__file__).parent / folder
    folder_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created/verified output directory: {folder_path}")

logger.info("[OUTPUT DIRECTORIES READY]")
logger.info("[Analyze Contract → outputs/analysis_reports]")
logger.info("[Programme Validation → outputs/validation_reports]")
logger.info("[Report Generation → outputs/reports]")

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

app = FastAPI(
    title="NEC Engineering Analysis System",
    description="Backend API for comparing NEC contracts against Primavera P6 programmes",
    version="1.0.0"
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


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Home page with links to upload forms."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/favicon.ico")
async def favicon():
    """Handle favicon requests to prevent 404 errors."""
    from fastapi.responses import Response
    return Response(status_code=204)  # No Content


@app.get("/health")
async def health_check():
    """Health check endpoint."""
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


@app.get("/api/ai_mode")
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


@app.options("/api/{path:path}")
async def options_handler(path: str):
    """Handle CORS preflight requests."""
    from fastapi.responses import Response
    return Response(status_code=200)

