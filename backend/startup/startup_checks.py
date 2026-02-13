"""
Operational startup checks (no engine or acceptability logic).
Configuration validation and integrity self-check. Fail fast on misconfiguration.
"""

import logging
from pathlib import Path

from app.persistence.integrity import compute_record_hash
from app.runtime_paths import RUNTIME_DIR
from app.security_config import (
    MAX_XER_FILE_SIZE_BYTES,
    REQUEST_SIZE_LIMIT_BYTES,
    RATE_LIMIT_PER_MINUTE,
    REQUIRE_API_KEY,
    get_valid_api_keys,
    rate_limit_dir,
    audit_log_path,
)

logger = logging.getLogger(__name__)

# Required output / ledger directories (under project root / runtime)
REQUIRED_DIRS = [
    "analysis_reports",
    "validation_reports",
    "reports",
    "idempotency",
    "rate_limit",
    "submission_history",
    "acceptance_history",
]


def run_config_validation() -> None:
    """
    Validate security and operational config. Raises RuntimeError if invalid.
    """
    if MAX_XER_FILE_SIZE_BYTES <= 0:
        raise RuntimeError(
            "Configuration error: MAX_XER_FILE_SIZE_MB must be > 0. "
            f"Got MAX_XER_FILE_SIZE_BYTES={MAX_XER_FILE_SIZE_BYTES}."
        )
    if REQUEST_SIZE_LIMIT_BYTES < MAX_XER_FILE_SIZE_BYTES:
        raise RuntimeError(
            "Configuration error: REQUEST_SIZE_LIMIT_MB must be >= MAX_XER_FILE_SIZE_MB. "
            f"Got REQUEST_SIZE_LIMIT_BYTES={REQUEST_SIZE_LIMIT_BYTES}, MAX_XER_FILE_SIZE_BYTES={MAX_XER_FILE_SIZE_BYTES}."
        )
    if RATE_LIMIT_PER_MINUTE <= 0:
        raise RuntimeError(
            "Configuration error: RATE_LIMIT_PER_MINUTE must be > 0. "
            f"Got {RATE_LIMIT_PER_MINUTE}."
        )
    if REQUIRE_API_KEY and not get_valid_api_keys():
        raise RuntimeError(
            "Configuration error: REQUIRE_API_KEY is true but VALID_API_KEYS is empty or not set. "
            "Set VALID_API_KEYS (comma-separated) or set REQUIRE_API_KEY=false."
        )


def run_integrity_self_check() -> None:
    """
    Verify output directories exist, sample hash works, ledger dirs accessible.
    Raises RuntimeError if misconfigured.
    """
    for rel in REQUIRED_DIRS:
        d = RUNTIME_DIR / rel
        d.mkdir(parents=True, exist_ok=True)
        if not d.is_dir():
            raise RuntimeError(f"Integrity check failed: required directory is not a directory: {d}")
        try:
            (d / ".write_check").write_text("ok")
            (d / ".write_check").unlink()
        except OSError as e:
            raise RuntimeError(f"Integrity check failed: directory not writable: {d}. {e}")

    try:
        h = compute_record_hash({"test": 1, "nested": {"a": 2}})
        if not h or len(h) != 64:
            raise RuntimeError("Integrity check failed: sample hash computation produced invalid result.")
    except Exception as e:
        raise RuntimeError(f"Integrity check failed: sample hash computation failed: {e}")

    try:
        rate_limit_dir().mkdir(parents=True, exist_ok=True)
        audit_log_path().parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise RuntimeError(f"Integrity check failed: ledger/audit directories not accessible: {e}")

    logger.info("[STARTUP] Integrity self-check passed.")


def check_ledger_accessible() -> None:
    """
    Lightweight check that ledger/output dirs are accessible. Used by health endpoint.
    Raises RuntimeError if not.
    """
    for rel in ["submission_history", "acceptance_history", "idempotency"]:
        d = RUNTIME_DIR / rel
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
        if not d.is_dir():
            raise RuntimeError(f"Ledger check failed: not a directory: {d}")
    try:
        compute_record_hash({"health": "check"})
    except Exception as e:
        raise RuntimeError(f"Ledger check failed: integrity hash failed: {e}")
