"""
Security hardening configuration (API layer only).
Read from environment; no validator or persistence logic.
Outputs (rate limit, audit log) go to project root / runtime.
"""

import os
from pathlib import Path

from app.runtime_paths import RUNTIME_DIR


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)).strip())
    except ValueError:
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    v = (os.getenv(key) or "").strip().lower()
    return v in ("1", "true", "yes") if v else default


# Max XER file size in bytes (default 25MB)
MAX_XER_FILE_SIZE_BYTES: int = _env_int("MAX_XER_FILE_SIZE_MB", 25) * 1024 * 1024

# Global request body size limit in bytes (default 26MB, slightly above XER limit for multipart overhead)
REQUEST_SIZE_LIMIT_BYTES: int = _env_int("REQUEST_SIZE_LIMIT_MB", 26) * 1024 * 1024

# Rate limit: requests per minute per IP
RATE_LIMIT_PER_MINUTE: int = max(1, _env_int("RATE_LIMIT_PER_MINUTE", 30))

# API key: if true, X-API-Key header must match VALID_API_KEYS
REQUIRE_API_KEY: bool = _env_bool("REQUIRE_API_KEY", False)

# Comma-separated list of valid API keys
def get_valid_api_keys() -> set:
    raw = (os.getenv("VALID_API_KEYS") or "").strip()
    return {k.strip() for k in raw.split(",") if k.strip()}


def rate_limit_dir() -> Path:
    """Directory for rate-limit counter files (under project root / runtime)."""
    p = RUNTIME_DIR / "rate_limit"
    p.mkdir(parents=True, exist_ok=True)
    return p


def audit_log_path() -> Path:
    """Append-only audit log file (under project root / runtime)."""
    return RUNTIME_DIR / "api_audit.log"
