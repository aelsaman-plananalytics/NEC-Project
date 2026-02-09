"""
Email verification via ZeroBounce API.
When EMAIL_VERIFICATION_API_KEY is set, signup checks that the email is deliverable
before creating an account. If the API key is empty, verification is skipped.
"""

import logging
from typing import Optional, Tuple
from urllib.parse import quote

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

ZEROBOUNCE_BASE_URL = "https://api.zerobounce.net/v2/validate"
TIMEOUT_SECONDS = 15

# Only this status is considered acceptable for signup
VALID_STATUS = "valid"


def is_email_deliverable(email: str) -> Tuple[bool, Optional[str]]:
    """
    Check if the email is deliverable using ZeroBounce (if configured).

    Returns:
        (True, None) if email is valid / verification skipped.
        (False, "user message") if email failed verification or API error message.
    """
    api_key = (settings.EMAIL_VERIFICATION_API_KEY or "").strip()
    if not api_key:
        return True, None

    email = (email or "").strip().lower()
    if not email:
        return False, "Email is required."

    try:
        url = f"{ZEROBOUNCE_BASE_URL}?api_key={quote(api_key)}&email={quote(email)}"
        with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
            resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            logger.warning("ZeroBounce rate limit hit during email verification")
            return False, "Email verification is temporarily unavailable. Please try again shortly."
        try:
            err_body = e.response.json()
            err_msg = err_body.get("error", str(e))
        except Exception:
            err_msg = str(e)
        logger.warning("ZeroBounce API error: %s", err_msg)
        return False, "We couldn't verify this email address. Please check it or try again later."
    except (httpx.RequestError, Exception) as e:
        logger.warning("Email verification request failed: %s", e)
        return False, "Email verification is temporarily unavailable. Please try again later."

    status = (data.get("status") or "").strip().lower()
    if status == VALID_STATUS:
        return True, None

    if status in ("invalid", "spamtrap", "abuse", "do_not_mail"):
        return False, "This email address could not be verified. Please use a different address."
    if status in ("catch-all", "unknown"):
        return False, "We couldn't confirm this email address exists. Please use a different address or try again later."

    return False, "This email address could not be verified. Please use a different address."
