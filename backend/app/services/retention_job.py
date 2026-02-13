"""
Data retention enforcement: delete analysis runs older than user.data_retention_days.
Also resets runs_this_month when current date > user.runs_reset_date (plan gating).
Designed to be run by scheduler every 24h (not on startup).
"""

import logging
from datetime import datetime, timedelta, date

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user import User
from app.models.analysis_run import AnalysisRun

logger = logging.getLogger(__name__)


def _next_month_first(d: date) -> date:
    """First day of the month following d."""
    if d.month == 12:
        return d.replace(year=d.year + 1, month=1, day=1)
    return d.replace(month=d.month + 1, day=1)


def run_retention_cleanup() -> dict:
    """
    For each user, delete analysis_runs where created_at is older than user.data_retention_days.
    Returns {"users_processed": int, "runs_deleted": int, "errors": list}.
    """
    db: Session = SessionLocal()
    total_deleted = 0
    users_processed = 0
    errors = []
    try:
        users = db.query(User).all()
        now = datetime.utcnow()
        for user in users:
            try:
                days = getattr(user, "data_retention_days", None) or 365
                if days <= 0:
                    continue
                cutoff = now - timedelta(days=days)
                deleted = (
                    db.query(AnalysisRun)
                    .filter(
                        AnalysisRun.user_id == user.id,
                        AnalysisRun.created_at < cutoff,
                    )
                    .delete()
                )
                if deleted:
                    total_deleted += deleted
                    logger.info(
                        "Retention: user_id=%s data_retention_days=%s deleted %s run(s) older than %s",
                        user.id,
                        days,
                        deleted,
                        cutoff.isoformat(),
                    )
                users_processed += 1
            except Exception as e:
                errors.append({"user_id": getattr(user, "id", None), "error": str(e)})
                logger.warning("Retention cleanup failed for user %s: %s", getattr(user, "id", None), e)
        # Plan gating: reset runs_this_month when current date > runs_reset_date
        today = date.today()
        for user in users:
            try:
                reset_date = getattr(user, "runs_reset_date", None)
                if reset_date is not None and today > reset_date:
                    user.runs_this_month = 0
                    user.runs_reset_date = _next_month_first(today)
                    logger.info("Retention: user_id=%s runs_this_month reset to 0, next reset %s", user.id, user.runs_reset_date)
            except Exception as e:
                errors.append({"user_id": getattr(user, "id", None), "error": str(e)})
        db.commit()
    except Exception as e:
        db.rollback()
        errors.append({"scope": "retention_job", "error": str(e)})
        logger.exception("Retention job failed: %s", e)
    finally:
        db.close()
    return {"users_processed": users_processed, "runs_deleted": total_deleted, "errors": errors}
