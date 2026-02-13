"""
Single source of truth for runtime/output directory (project root / runtime).
All file outputs (reports, idempotency, audit log, etc.) go under RUNTIME_DIR.
Override with environment variable RUNTIME_DIR.
"""

import os
from pathlib import Path

# backend/app/runtime_paths.py -> app -> backend -> project root
_APP_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _APP_DIR.parent
_PROJECT_ROOT = _BACKEND_DIR.parent

RUNTIME_DIR = Path(os.getenv("RUNTIME_DIR", str(_PROJECT_ROOT / "runtime")))


def get_runtime_dir() -> Path:
    """Return the runtime directory (project root / runtime)."""
    return RUNTIME_DIR
