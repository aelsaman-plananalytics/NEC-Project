"""
Auth router: signup, login, get/update current user.
Uses PostgreSQL (User model) and JWT.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, DEFAULT_PREFERENCES
from app.schemas.auth import (
    SignupRequest,
    LoginRequest,
    UserResponse,
    UserUpdate,
    TokenResponse,
)
from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    get_user_by_email,
    get_user_by_id,
)
from app.services.email_verification import is_email_deliverable
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
    )


@router.post("/signup", response_model=TokenResponse)
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
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=user_to_response(user))


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = get_user_by_email(db, data.email)
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=user_to_response(user))


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
