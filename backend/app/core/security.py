from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import settings


# ---------------------------------------------------------
# Password hashing
# ---------------------------------------------------------

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """
    Hash a plain-text password using a secure password
    hashing algorithm provided by pwdlib.
    """
    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """
    Verify a plain-text password against its stored hash.
    """
    return password_hash.verify(
        plain_password,
        hashed_password,
    )


# ---------------------------------------------------------
# JWT
# ---------------------------------------------------------

ALGORITHM = "HS256"


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a JWT access token.

    The subject normally contains the user's database ID.
    """

    now = datetime.now(timezone.utc)

    if expires_delta is None:
        expires_delta = timedelta(
            minutes=settings.access_token_expire_minutes
        )

    expire = now + expires_delta

    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT access token.

    Raises jwt.PyJWTError if the token is invalid or expired.
    """

    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=[ALGORITHM],
    )
