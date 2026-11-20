import re
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user_profile import UserProfile
from app.models.user_setting import UserSetting

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import require_role
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import UserResponse


router = APIRouter(prefix="/users", tags=["Users"])


class AdminUserCreateRequest(BaseModel):
    model_config = {"str_strip_whitespace": True}

    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role_id: int = Field(gt=0)
    department: str | None = Field(default=None, max_length=100)


class AdminUserStatusUpdate(BaseModel):
    is_active: bool


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=150)
    phone: str | None = Field(None, max_length=30)
    department: str | None = Field(None, max_length=100)


PHONE_RE = re.compile(r"^\+?\(?[0-9][0-9\s()\-]{6,24}$")
DEFAULT_TIMEZONE = "Asia/Kolkata"
SESSION_TIMEOUTS = {15, 30, 60, 120, 480}
USER_COLUMN_FIELDS = {"phone", "department"}
PROFILE_COLUMN_FIELDS = {"job_title", "location", "bio"}
OPTIONAL_FIELDS = USER_COLUMN_FIELDS | PROFILE_COLUMN_FIELDS


def _check_phone(value: str | None) -> str | None:
    if value is not None and value.strip() and not PHONE_RE.match(value.strip()):
        raise ValueError("Enter a valid phone number (digits, spaces, + ( ) - only).")
    return value


class FullProfileUpdate(BaseModel):
    """Create/update profile details. Omitted fields are left unchanged;
    an empty string clears an optional field."""

    full_name: str | None = Field(None, min_length=2, max_length=150)
    phone: str | None = Field(None, max_length=30)
    department: str | None = Field(None, max_length=100)
    job_title: str | None = Field(None, max_length=100)
    location: str | None = Field(None, max_length=100)
    bio: str | None = Field(None, max_length=500)
    timezone: str | None = Field(None, max_length=64)

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, value):
        return _check_phone(value)

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, value):
        if value:
            try:
                ZoneInfo(value)
            except Exception:
                raise ValueError("Unknown timezone. Use an IANA name such as Asia/Kolkata.")
        return value


class SettingsUpdate(BaseModel):
    email_notifications: bool | None = None
    task_notifications: bool | None = None
    security_alerts: bool | None = None
    weekly_reports: bool | None = None
    session_timeout_minutes: int | None = None

    @field_validator("session_timeout_minutes")
    @classmethod
    def _check_timeout(cls, value):
        if value is not None and value not in SESSION_TIMEOUTS:
            raise ValueError("Session timeout must be 15, 30, 60, 120 or 480 minutes.")
        return value


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


def _profile_row(db: Session, user_id: int) -> UserProfile | None:
    return db.get(UserProfile, user_id)


def _serialize_profile(user: User, profile: UserProfile | None) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "fullName": user.full_name,
        "roleName": user.role_name,
        "isActive": user.is_active,
        "createdAt": user.created_at.isoformat() if user.created_at else None,
        "phone": user.phone,
        "department": user.department,
        "jobTitle": profile.job_title if profile else None,
        "location": profile.location if profile else None,
        "bio": profile.bio if profile else None,
        "timezone": profile.timezone if profile else DEFAULT_TIMEZONE,
    }


def _serialize_settings(row: UserSetting | None) -> dict:
    return {
        "emailNotifications": row.email_notifications if row else True,
        "taskNotifications": row.task_notifications if row else True,
        "securityAlerts": row.security_alerts if row else True,
        "weeklyReports": row.weekly_reports if row else False,
        "sessionTimeoutMinutes": row.session_timeout_minutes if row else 30,
        "isCustomised": row is not None,
    }


# NOTE: every endpoint below operates only on get_current_user - there is no
# user id in any path, so a user can never read or change someone else's data.
@router.get("/finance-users")
def list_finance_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return active same-tenant Finance Users for invoice payment assignment."""
    if current_user.role_name not in {"Finance User", "Finance Manager", "Chief Accountant"}:
        raise HTTPException(status_code=403, detail="Only finance workflow roles can view payment assignees.")
    rows = db.scalars(
        select(User).join(Role, User.role_id == Role.id).where(
            User.tenant_id == current_user.tenant_id,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
            Role.name == "Finance User",
        ).order_by(User.full_name.asc())
    ).all()
    return [{"id": row.id, "fullName": row.full_name, "email": row.email} for row in rows]


@router.get("/me/profile")
def read_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _serialize_profile(current_user, _profile_row(db, current_user.id))


@router.put("/me/profile")
def save_profile(
    payload: FullProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    profile = _profile_row(db, current_user.id)

    if "full_name" in data and data["full_name"] is not None:
        name = data["full_name"].strip()
        if len(name) < 2:
            raise HTTPException(status_code=422, detail="Full name must be at least 2 characters.")
        current_user.full_name = name

    for field in USER_COLUMN_FIELDS & data.keys():
        setattr(current_user, field, (data[field] or "").strip() or None)

    if (PROFILE_COLUMN_FIELDS | {"timezone"}) & data.keys():
        if profile is None:
            profile = UserProfile(user_id=current_user.id, timezone=DEFAULT_TIMEZONE)
            db.add(profile)
        for field in PROFILE_COLUMN_FIELDS & data.keys():
            setattr(profile, field, (data[field] or "").strip() or None)
        if data.get("timezone"):
            profile.timezone = data["timezone"]

    db.commit()
    db.refresh(current_user)
    return _serialize_profile(current_user, _profile_row(db, current_user.id))


@router.delete("/me/profile/{field}")
def delete_profile_field(
    field: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Clear one optional detail. Name, email, role and password cannot be deleted."""
    if field not in OPTIONAL_FIELDS:
        raise HTTPException(status_code=400, detail="This field cannot be deleted.")

    if field in USER_COLUMN_FIELDS:
        setattr(current_user, field, None)
    else:
        profile = _profile_row(db, current_user.id)
        if profile is not None:
            setattr(profile, field, None)

    db.commit()
    db.refresh(current_user)
    return _serialize_profile(current_user, _profile_row(db, current_user.id))


@router.get("/me/settings")
def read_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _serialize_settings(db.get(UserSetting, current_user.id))


@router.patch("/me/settings")
def save_settings(
    payload: SettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.get(UserSetting, current_user.id)
    if row is None:
        row = UserSetting(
            user_id=current_user.id,
            email_notifications=True,
            task_notifications=True,
            security_alerts=True,
            weekly_reports=False,
            session_timeout_minutes=30,
        )
        db.add(row)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return _serialize_settings(row)


@router.delete("/me/settings")
def reset_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete the saved preferences so the defaults apply again."""
    row = db.get(UserSetting, current_user.id)
    if row is not None:
        db.delete(row)
        db.commit()
    return _serialize_settings(None)


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must differ from the current one.")
    current_user.password_hash = hash_password(payload.new_password)
    db.commit()


@router.get("/me", response_model=UserResponse)
def get_my_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
def update_my_profile(
    updates: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update mutable profile fields for the current user."""
    changed = False

    if updates.full_name is not None:
        trimmed = updates.full_name.strip()
        if len(trimmed) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Full name must be at least 2 characters.",
            )
        current_user.full_name = trimmed
        changed = True

    if updates.phone is not None:
        current_user.phone = updates.phone.strip() or None
        changed = True

    if updates.department is not None:
        current_user.department = updates.department.strip() or None
        changed = True

    if changed:
        db.add(current_user)
        db.commit()
        db.refresh(current_user)

    return current_user


@router.get("/admin-test")
def admin_test(
    current_user: User = Depends(require_role("Administrator")),
):
    return {
        "message": "Administrator access granted.",
        "user_id": current_user.id,
        "role": current_user.role.name,
    }

# Administrator-only user management. Public signup remains on /auth/signup
# and continues assigning the Employee / Requester role automatically.
@router.get("/admin/roles")
def admin_list_roles(
    current_user: User = Depends(require_role("Administrator")),
    db: Session = Depends(get_db),
):
    roles = db.scalars(select(Role).order_by(Role.id.asc())).all()
    return [{"id": role.id, "name": role.name, "description": role.description} for role in roles]


@router.get("/admin/users", response_model=list[UserResponse])
def admin_list_users(
    current_user: User = Depends(require_role("Administrator")),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(User).where(User.tenant_id == current_user.tenant_id, User.deleted_at.is_(None))
        .order_by(User.created_at.desc(), User.id.desc())
    ).all()


@router.post("/admin/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def admin_create_user(
    payload: AdminUserCreateRequest,
    current_user: User = Depends(require_role("Administrator")),
    db: Session = Depends(get_db),
):
    email = str(payload.email).strip().lower()
    existing = db.scalar(select(User).where(func.lower(User.email) == email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists.")

    role = db.get(Role, payload.role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Selected role does not exist.")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role_id=role.id,
        tenant_id=current_user.tenant_id,
        department=(payload.department or "").strip() or None,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        print("ADMIN USER CREATE INTEGRITY ERROR:", repr(exc.orig))
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Database integrity error. Check backend logs."
        ) from exc
    db.refresh(user)
    return user


@router.patch("/admin/users/{user_id}/status", response_model=UserResponse)
def admin_update_user_status(
    user_id: int,
    payload: AdminUserStatusUpdate,
    current_user: User = Depends(require_role("Administrator")),
    db: Session = Depends(get_db),
):
    target = db.scalar(select(User).where(User.id == user_id, User.tenant_id == current_user.tenant_id, User.deleted_at.is_(None)))
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if target.id == current_user.id and not payload.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate your own account.")

    if not payload.is_active and (target.role_name or "").strip().casefold() == "administrator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator accounts cannot be deactivated from User Management.",
        )

    target.is_active = payload.is_active
    db.commit()
    db.refresh(target)
    return target


@router.delete("/admin/users/{user_id}")
def admin_archive_user(
    user_id: int,
    current_user: User = Depends(require_role("Administrator")),
    db: Session = Depends(get_db),
):
    target = db.scalar(select(User).where(User.id == user_id, User.tenant_id == current_user.tenant_id))

    if target is None or target.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if target.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot archive your own account.",
        )

    if (target.role_name or "").strip().casefold() == "administrator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator accounts cannot be archived.",
        )

    from datetime import datetime, timezone

    target.deleted_at = datetime.now(timezone.utc)
    target.is_active = False
    db.commit()

    return {"message": "User archived successfully.", "user_id": target.id}
