"""
Simple file-based rate limiting per IP (API layer only).
Store under project root / runtime/rate_limit. Returns 429 when limit exceeded.
"""

import json
import re
import time
from pathlib import Path
from typing import Tuple

from app.security_config import rate_limit_dir, RATE_LIMIT_PER_MINUTE


def _safe_filename(ip: str) -> str:
    """Safe filename from IP."""
    return re.sub(r"[^a-zA-Z0-9._-]", "_", (ip or "unknown").strip()) or "unknown"


def _get_window_path(ip: str) -> Path:
    return rate_limit_dir() / f"{_safe_filename(ip)}.json"


def check_rate_limit(ip: str) -> Tuple[bool, int]:
    """
    Check if request is within rate limit. Returns (allowed, current_count).
    Side effect: records this request if allowed.
    """
    path = _get_window_path(ip)
    now = time.time()
    window_sec = 60.0
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            timestamps = data.get("requests") or []
        else:
            timestamps = []
    except (json.JSONDecodeError, OSError):
        timestamps = []
    # Drop requests older than 1 minute
    cutoff = now - window_sec
    timestamps = [t for t in timestamps if t >= cutoff]
    if len(timestamps) >= RATE_LIMIT_PER_MINUTE:
        return False, len(timestamps)
    timestamps.append(now)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"requests": timestamps}, f)
    except OSError:
        pass
    return True, len(timestamps)
