"""
Structured error contract for API responses.

All error responses use:
  { "error_code": "...", "error_message": "...", "details": ... }
"""

from typing import Any, Dict, Optional
from fastapi.responses import JSONResponse


# Error codes used by the API layer (no business logic).
VALIDATION_GUARDRAIL_ERROR = "VALIDATION_GUARDRAIL_ERROR"
LEDGER_INTEGRITY_ERROR = "LEDGER_INTEGRITY_ERROR"
NOT_FOUND = "NOT_FOUND"
BAD_REQUEST = "BAD_REQUEST"
IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
INTERNAL_ERROR = "INTERNAL_ERROR"
# Security hardening
REQUEST_TOO_LARGE = "REQUEST_TOO_LARGE"
RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
UNAUTHORIZED = "UNAUTHORIZED"
PLAN_LIMIT_EXCEEDED = "PLAN_LIMIT_EXCEEDED"


def _error_body(
    error_code: str,
    error_message: str,
    details: Optional[Any] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "error_code": error_code,
        "error_message": error_message,
    }
    if details is not None:
        out["details"] = details
    return out


def structured_error_response(
    status_code: int,
    error_code: str,
    error_message: str,
    details: Optional[Any] = None,
) -> JSONResponse:
    """Return a JSONResponse with the standard error contract."""
    return JSONResponse(
        status_code=status_code,
        content=_error_body(error_code, error_message, details),
    )


def error_code_from_runtime_error(message: str) -> str:
    """Map RuntimeError message to error_code. Does not modify validator or persistence."""
    msg = (message or "").lower()
    if "ledger chain" in msg or "ledger chain integrity" in msg:
        return LEDGER_INTEGRITY_ERROR
    if "submission guard" in msg or "guard" in msg and ("acceptability" in msg or "validation" in msg):
        return VALIDATION_GUARDRAIL_ERROR
    if "not found" in msg or "does not exist" in msg or "submission not found" in msg:
        return NOT_FOUND
    return INTERNAL_ERROR
