from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from app.models.user_setting import UserSetting
from app.models.auth_token import UserAuthToken
from app.models.user import User
from app.core.security import hash_password
from app.services.email_delivery import send_email
from app.core.config import settings
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field

from app.core.database import get_db
from app.core.security import create_access_token
from app.schemas.auth import (
    LoginRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
)
def signup(
    signup_data: SignupRequest,
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.create_user(db, signup_data)
        response = UserResponse.model_validate(user).model_dump()
        response.update({
            "message": "Account created successfully. You can sign in now.",
            "verificationRequired": False,
            "verificationEmailSent": False,
        })
        return response

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        ) from exc




class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


@router.post("/verify-email")
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    token_row = db.scalar(select(UserAuthToken).where(
        UserAuthToken.token_hash == token_hash,
        UserAuthToken.purpose == "EMAIL_VERIFY",
        UserAuthToken.used_at.is_(None),
        UserAuthToken.expires_at > now,
    ).with_for_update())
    if token_row is None:
        raise HTTPException(status_code=400, detail="This verification link is invalid or expired. Request a new one.")
    user = db.get(User, token_row.user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise HTTPException(status_code=400, detail="This verification link is no longer valid.")
    user.is_verified = True
    token_row.used_at = now
    for other in db.scalars(select(UserAuthToken).where(UserAuthToken.user_id == user.id,
            UserAuthToken.purpose == "EMAIL_VERIFY", UserAuthToken.used_at.is_(None), UserAuthToken.id != token_row.id)).all():
        other.used_at = now
    db.commit()
    return {"message": "Email verified. You can now sign in."}


@router.post("/resend-verification")
def resend_verification(payload: ResendVerificationRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email, User.is_active.is_(True), User.deleted_at.is_(None)))
    if user is not None and not user.is_verified and all((settings.smtp_host, settings.smtp_username, settings.smtp_password, settings.smtp_from_email)):
        now = datetime.now(timezone.utc)
        raw_token = secrets.token_urlsafe(36)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        db.add(UserAuthToken(user_id=user.id, purpose="EMAIL_VERIFY", token_hash=token_hash, expires_at=now + timedelta(hours=24)))
        db.commit()
        try:
            send_email(user.email, "Verify your Azentmart Finance AI account",
                       f"Verify your email within 24 hours:\n\n{settings.frontend_url}/verify-email?token={raw_token}")
        except Exception:
            db.rollback()
    return {"message": "If the account needs verification, a new verification email will be sent."}


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Always return the same response to avoid disclosing registered emails."""
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email, User.is_active.is_(True), User.deleted_at.is_(None)))
    if user is not None and settings.smtp_host and settings.smtp_username and settings.smtp_password and settings.smtp_from_email:
        raw_token = secrets.token_urlsafe(36)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc)
        db.add(UserAuthToken(user_id=user.id, purpose="PASSWORD_RESET", token_hash=token_hash, expires_at=now + timedelta(minutes=30)))
        db.commit()
        link = f"{settings.frontend_url}/reset-password?token={raw_token}"
        try:
            send_email(
                user.email,
                "Reset your Azentmart Finance AI password",
                f"Use this one-time link within 30 minutes to reset your password:\n\n{link}\n\nIf you did not request this, ignore this email.",
            )
        except Exception:
            # Do not disclose whether the account exists or whether delivery failed.
            db.rollback()
    return {"message": "If an active account exists for that email, password reset instructions will be sent."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    if len(payload.new_password) < 8 or len(payload.new_password) > 128:
        raise HTTPException(status_code=422, detail="Password must be between 8 and 128 characters.")
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    token_row = db.scalar(select(UserAuthToken).where(
        UserAuthToken.token_hash == token_hash,
        UserAuthToken.purpose == "PASSWORD_RESET",
        UserAuthToken.used_at.is_(None),
        UserAuthToken.expires_at > now,
    ).with_for_update())
    if token_row is None:
        raise HTTPException(status_code=400, detail="This password reset link is invalid or expired. Request a new link.")
    user = db.get(User, token_row.user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise HTTPException(status_code=400, detail="This password reset link is no longer valid.")
    user.password_hash = hash_password(payload.new_password)
    token_row.used_at = now
    # Invalidate any other outstanding reset links for this account.
    for other in db.scalars(select(UserAuthToken).where(
        UserAuthToken.user_id == user.id,
        UserAuthToken.purpose == "PASSWORD_RESET",
        UserAuthToken.used_at.is_(None),
        UserAuthToken.id != token_row.id,
    )).all():
        other.used_at = now
    db.commit()
    return {"message": "Password updated successfully. You can now sign in."}


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.authenticate_user(db, login_data.email, login_data.password)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    saved = db.get(UserSetting, user.id)
    access_token = create_access_token(
        subject=str(user.id),
        expires_delta=(
            timedelta(minutes=saved.session_timeout_minutes) if saved else None
        ),
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
    )
