"""
Performance hardening: timeouts and structured duration logging.
Does not modify validator or acceptability logic.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

# Default timeouts (seconds)
CONTRACT_ANALYSIS_TIMEOUT = 300
XER_VALIDATION_TIMEOUT = 600

T = TypeVar("T")


def run_with_timeout(
    fn: Callable[[], T],
    timeout_seconds: float,
    step_name: str = "operation",
) -> T:
    """
    Run a synchronous callable in a thread with a timeout.
    Raises TimeoutError if the callable does not complete within timeout_seconds.
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError:
            logger.warning(
                "Timeout after %.1fs in %s",
                timeout_seconds,
                step_name,
                extra={"event": "timeout", "step": step_name, "timeout_seconds": timeout_seconds},
            )
            raise TimeoutError(f"{step_name} did not complete within {timeout_seconds}s")


def log_performance_metric(step: str, duration_ms: float, **extra: object) -> None:
    """Log a structured performance metric (JSON-friendly)."""
    payload = {
        "event": "performance_metric",
        "step": step,
        "duration_ms": round(duration_ms, 2),
        **extra,
    }
    logger.info("%s", payload, extra=payload)
