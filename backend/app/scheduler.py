"""
Background scheduler for retention cleanup and plan resets.
Uses APScheduler; started on app startup, shut down gracefully on shutdown.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_scheduler: Optional["BackgroundScheduler"] = None


def get_scheduler() -> Optional["BackgroundScheduler"]:
    """Return the global scheduler instance, or None if not started."""
    return _scheduler


def start_scheduler() -> None:
    """Start the background scheduler and add the retention job (every 24h)."""
    global _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from app.services.retention_job import run_retention_cleanup
    except ImportError as e:
        logger.warning("[SCHEDULER] APScheduler not available: %s. Retention will not run on a schedule.", e)
        return
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        run_retention_cleanup,
        "interval",
        hours=24,
        id="retention_cleanup",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("[SCHEDULER] Started; retention_cleanup scheduled every 24h.")


def shutdown_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler is None:
        return
    try:
        _scheduler.shutdown(wait=True)
        logger.info("[SCHEDULER] Shut down gracefully.")
    except Exception as e:
        logger.warning("[SCHEDULER] Shutdown error: %s", e)
    _scheduler = None
