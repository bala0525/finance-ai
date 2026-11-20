from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128,
    )

    full_name: str = Field(
        min_length=2,
        max_length=150,
    )


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    is_verified: bool
    role_id: int
    role_name: str | None = None
    can_review: bool = False
    phone: str | None = None
    department: str | None = None
    created_at: datetime | None = None
    # Highest invoice total the user may approve (INR). null = unlimited
    # for administrators; always check can_review first.
    approval_limit: float | None = None


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr

    password: str = Field(
        min_length=1,
        max_length=128,
    )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
