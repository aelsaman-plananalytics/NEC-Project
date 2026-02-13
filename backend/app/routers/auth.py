"""
Auth router: signup, login, get/update current user, email verification.
Uses PostgreSQL (User model) and JWT.
"""

import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User, DEFAULT_PREFERENCES
from app.schemas.auth import (
    SignupRequest,
    LoginRequest,
    UserResponse,
    UserUpdate,
    TokenResponse,
    SignupSuccessResponse,
    ResendVerificationRequest,
    RequestPasswordResetRequest,
    ResetPasswordRequest,
)
from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    get_user_by_email,
    get_user_by_id,
    get_user_by_verification_token,
    get_user_by_password_reset_token,
)
from app.services.email_verification import is_email_deliverable
from app.services.smtp_email import (
    send_verification_email,
    build_verification_link,
    send_password_reset_email,
    build_reset_password_link,
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

router = APIRouter(prefix="/api/auth", tags=["auth"])

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User | None:
    """Return current user if valid token present, else None. Used when auth is optional (e.g. report with run_id)."""
    if not credentials or not credentials.credentials:
        return None
    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        return None
    return get_user_by_id(db, user_id)


def user_to_response(user: User) -> UserResponse:
    prefs = getattr(user, "preferences", None)
    if prefs is None:
        prefs = DEFAULT_PREFERENCES
    elif isinstance(prefs, dict):
        prefs = {**DEFAULT_PREFERENCES, **prefs}
    else:
        prefs = DEFAULT_PREFERENCES
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name or "",
        organisation=user.organisation or "",
        role=user.role or "Consultant",
        timezone=user.timezone or "UTC",
        report_naming_preference=user.report_naming_preference or "contract_date_validation",
        data_retention_days=user.data_retention_days or 365,
        organisation_logo_url=getattr(user, "organisation_logo_url", None) or None,
        preferences=prefs,
        is_verified=getattr(user, "is_verified", True),
    )


VERIFICATION_EXPIRY_HOURS = 24
PASSWORD_RESET_EXPIRY_HOURS = 1


def _set_verification_token(user: User, db: Session) -> str:
    """Set a new verification token and expiry on user; commit; return the token."""
    token = secrets.token_urlsafe(32)
    user.email_verification_token = token
    user.email_verification_expires = datetime.utcnow() + timedelta(hours=VERIFICATION_EXPIRY_HOURS)
    db.commit()
    return token


@router.post("/signup", response_model=SignupSuccessResponse)
def signup(data: SignupRequest, db: Session = Depends(get_db)):
    if get_user_by_email(db, data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )
    ok, msg = is_email_deliverable(data.email)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg or "This email address could not be verified.",
        )
    user = User(
        email=data.email.strip().lower(),
        hashed_password=hash_password(data.password),
        name=(data.name or "").strip() or data.email.split("@")[0],
        organisation=(data.organisation or "").strip(),
        is_verified=not settings.REQUIRE_EMAIL_VERIFICATION,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    if settings.REQUIRE_EMAIL_VERIFICATION:
        verification_token = _set_verification_token(user, db)
        link = build_verification_link(verification_token, settings.FRONTEND_BASE_URL)
        send_verification_email(user.email, link, expires_hours=VERIFICATION_EXPIRY_HOURS)
        return SignupSuccessResponse(
            message="Check your email to verify your account before logging in.",
            email=user.email,
        )
    return SignupSuccessResponse(
        message="Account created. You can sign in now.",
        email=user.email,
    )


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = get_user_by_email(db, data.email)
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    if settings.REQUIRE_EMAIL_VERIFICATION and not getattr(user, "is_verified", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Please verify your email before logging in.",
                "error_code": "EMAIL_NOT_VERIFIED",
            },
        )
    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=user_to_response(user))


@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    """
    Verify email from link in verification email. Single-use; clears token and sets is_verified=True.
    """
    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Missing verification token.", "error_code": "INVALID_TOKEN"},
        )
    user = get_user_by_verification_token(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Invalid or expired verification link.", "error_code": "INVALID_TOKEN"},
        )
    now = datetime.utcnow()
    if user.email_verification_expires and user.email_verification_expires < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Verification link has expired. Request a new one.", "error_code": "EXPIRED"},
        )
    user.is_verified = True
    user.email_verification_token = None
    user.email_verification_expires = None
    db.commit()
    return {"message": "Email verified. You can now log in.", "email": user.email}


@router.post("/request-password-reset")
def request_password_reset(data: RequestPasswordResetRequest, db: Session = Depends(get_db)):
    """Send password reset email with token. Does not reveal whether email exists."""
    email = (data.email or "").strip().lower()
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required.")
    user = get_user_by_email(db, email)
    if not user:
        return {"message": "If an account exists for this email, you will receive a password reset link."}
    token = secrets.token_urlsafe(32)
    user.password_reset_token = token
    user.password_reset_expires = datetime.utcnow() + timedelta(hours=PASSWORD_RESET_EXPIRY_HOURS)
    db.commit()
    link = build_reset_password_link(token, settings.FRONTEND_BASE_URL)
    send_password_reset_email(user.email, link, expires_hours=PASSWORD_RESET_EXPIRY_HOURS)
    return {"message": "If an account exists for this email, you will receive a password reset link."}


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password using token from email. Single-use; invalidates token."""
    token = (data.token or "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Missing reset token.", "error_code": "INVALID_TOKEN"},
        )
    user = get_user_by_password_reset_token(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Invalid or expired reset link.", "error_code": "INVALID_TOKEN"},
        )
    now = datetime.utcnow()
    if getattr(user, "password_reset_expires", None) and user.password_reset_expires < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Reset link has expired. Request a new one.", "error_code": "EXPIRED"},
        )
    user.hashed_password = hash_password(data.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    db.commit()
    return {"message": "Password has been reset. You can now sign in."}


@router.post("/resend-verification")
def resend_verification(data: ResendVerificationRequest, db: Session = Depends(get_db)):
    """
    Resend verification email. Rate-limited (by IP via SecurityMiddleware). Generates new token and sends email.
    """
    email = (data.email or "").strip().lower()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required.",
        )
    user = get_user_by_email(db, email)
    if not user:
        # Do not reveal whether the email exists
        return {"message": "If an account exists for this email, a new verification link has been sent."}
    if getattr(user, "is_verified", True):
        return {"message": "This account is already verified. You can log in."}
    verification_token = _set_verification_token(user, db)
    link = build_verification_link(verification_token, settings.FRONTEND_BASE_URL)
    send_verification_email(user.email, link, expires_hours=VERIFICATION_EXPIRY_HOURS)
    return {"message": "Verification email sent. Check your inbox."}


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return user_to_response(current_user)


@router.patch("/me", response_model=UserResponse)
def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if data.name is not None:
        current_user.name = data.name
    if data.organisation is not None:
        current_user.organisation = data.organisation
    if data.role is not None:
        current_user.role = data.role
    if data.timezone is not None:
        current_user.timezone = data.timezone
    if data.report_naming_preference is not None:
        current_user.report_naming_preference = data.report_naming_preference
    if data.data_retention_days is not None:
        current_user.data_retention_days = data.data_retention_days
    if hasattr(current_user, "organisation_logo_url"):
        current_user.organisation_logo_url = data.organisation_logo_url
    if hasattr(current_user, "preferences") and data.preferences is not None:
        current = current_user.preferences or {}
        current_user.preferences = {**DEFAULT_PREFERENCES, **current, **data.preferences}
    db.commit()
    db.refresh(current_user)
    return user_to_response(current_user)
