"""Pydantic schemas for auth (signup, login, user response)."""

from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(..., min_length=8)
    name: str = ""
    organisation: str = ""


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    organisation: str
    role: str
    timezone: str
    report_naming_preference: str
    data_retention_days: int
    organisation_logo_url: str | None = None
    preferences: dict[str, Any] | None = None
    is_verified: bool = True


class UserUpdate(BaseModel):
    name: str | None = None
    organisation: str | None = None
    role: str | None = None
    timezone: str | None = None
    report_naming_preference: str | None = None
    data_retention_days: int | None = None
    organisation_logo_url: str | None = None
    preferences: dict[str, Any] | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class SignupSuccessResponse(BaseModel):
    """Returned when signup succeeds but email must be verified (no token until verified)."""
    message: str = "Check your email to verify your account before logging in."
    email: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class RequestPasswordResetRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)
