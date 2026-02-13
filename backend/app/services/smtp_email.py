"""
Send verification emails via SMTP (no Resend).
Uses smtplib and email.message.EmailMessage.
Config: SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM from environment.
"""

import logging
import smtplib
from email.message import EmailMessage
from typing import Optional
from urllib.parse import urljoin

from app.config import settings

logger = logging.getLogger(__name__)


def _smtp_configured() -> bool:
    host = (settings.SMTP_HOST or "").strip()
    from_addr = (settings.SMTP_FROM or "").strip()
    return bool(host and from_addr)


def send_verification_email(
    to_email: str,
    verification_link: str,
    *,
    expires_hours: int = 24,
) -> bool:
    """
    Send a single verification email. Returns True if sent, False if SMTP not configured or send failed.
    Does NOT raise; logs errors.
    """
    if not _smtp_configured():
        logger.warning("SMTP not configured (SMTP_HOST/SMTP_FROM). Skipping verification email.")
        return False

    to_email = (to_email or "").strip().lower()
    if not to_email:
        return False

    msg = EmailMessage()
    msg["Subject"] = "Verify your email — NEC Engineering Analysis"
    msg["From"] = settings.SMTP_FROM.strip()
    msg["To"] = to_email
    msg.set_content(
        f"""Hello,

Please verify your email address by clicking the link below. This link expires in {expires_hours} hours.

{verification_link}

If you did not create an account with NEC Engineering Analysis, you can ignore this email.

—
NEC Engineering Analysis
"""
    )
    # Optional HTML alternative
    msg.add_alternative(
        f"""<!DOCTYPE html><html><body>
<p>Please verify your email by clicking the link below (expires in {expires_hours} hours):</p>
<p><a href="{verification_link}">{verification_link}</a></p>
<p>If you did not create an account, you can ignore this email.</p>
</body></html>""",
        subtype="html",
    )

    try:
        with smtplib.SMTP(settings.SMTP_HOST.strip(), settings.SMTP_PORT, timeout=30) as smtp:
            if (settings.SMTP_USERNAME or "").strip():
                smtp.starttls()
                smtp.login(
                    settings.SMTP_USERNAME.strip(),
                    (settings.SMTP_PASSWORD or "").strip(),
                )
            smtp.send_message(msg)
        logger.info("Verification email sent to %s", to_email)
        return True
    except Exception as e:
        logger.exception("Failed to send verification email to %s: %s", to_email, e)
        return False


def build_verification_link(token: str, base_url: Optional[str] = None) -> str:
    """
    Build the full URL for the verify-email page with token.
    If base_url is not provided, returns a path-only link (frontend can prepend origin).
    """
    path = f"/verify-email?token={token}"
    if base_url:
        base_url = base_url.rstrip("/")
        return urljoin(base_url + "/", path.lstrip("/"))
    return path


def build_reset_password_link(token: str, base_url: Optional[str] = None) -> str:
    """Build the full URL for the reset-password page with token."""
    path = f"/reset-password?token={token}"
    if base_url:
        base_url = base_url.rstrip("/")
        return urljoin(base_url + "/", path.lstrip("/"))
    return path


def send_password_reset_email(
    to_email: str,
    reset_link: str,
    *,
    expires_hours: int = 1,
) -> bool:
    """Send password reset email. Returns True if sent."""
    if not _smtp_configured():
        logger.warning("SMTP not configured. Skipping password reset email.")
        return False
    to_email = (to_email or "").strip().lower()
    if not to_email:
        return False
    msg = EmailMessage()
    msg["Subject"] = "Reset your password — NEC Engineering Analysis"
    msg["From"] = settings.SMTP_FROM.strip()
    msg["To"] = to_email
    msg.set_content(
        f"""Hello,

You requested a password reset. Click the link below to set a new password. This link expires in {expires_hours} hour(s).

{reset_link}

If you did not request this, you can ignore this email.

—
NEC Engineering Analysis
"""
    )
    try:
        with smtplib.SMTP(settings.SMTP_HOST.strip(), settings.SMTP_PORT, timeout=30) as smtp:
            if (settings.SMTP_USERNAME or "").strip():
                smtp.starttls()
                smtp.login(
                    settings.SMTP_USERNAME.strip(),
                    (settings.SMTP_PASSWORD or "").strip(),
                )
            smtp.send_message(msg)
        logger.info("Password reset email sent to %s", to_email)
        return True
    except Exception as e:
        logger.exception("Failed to send password reset email to %s: %s", to_email, e)
        return False
