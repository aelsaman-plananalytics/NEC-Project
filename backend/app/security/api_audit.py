"""
Append-only API audit log (API layer only).
Structured JSON lines: timestamp, ip, route, status, response_signature, idempotency_key.
Uses storage abstraction.
"""

import json
import re
from datetime import datetime, timezone
from typing import Optional


def _sanitize(s: Optional[str]) -> str:
    """One line, no newlines."""
    if s is None:
        return ""
    return re.sub(r"[\r\n\t]", " ", str(s).strip())[:500]


def log_api_request(
    ip: str,
    route: str,
    status_code: int,
    idempotency_key: Optional[str] = None,
    response_signature: Optional[str] = None,
    comparison_mode: Optional[str] = None,
) -> None:
    """Append one JSON line to api_audit.log (structured logging)."""
    from app.storage import get_storage
    ts = datetime.now(timezone.utc).isoformat()
    payload = {
        "timestamp": ts,
        "ip": _sanitize(ip),
        "route": _sanitize(route),
        "status": status_code,
        "response_signature": _sanitize(response_signature) if response_signature else None,
        "idempotency_key": _sanitize(idempotency_key) if idempotency_key else None,
        "comparison_mode": _sanitize(comparison_mode) if comparison_mode else None,
    }
    line = json.dumps(payload, ensure_ascii=False) + "\n"
    get_storage().append_line("api_audit.log", line)
