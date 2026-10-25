import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings
from app.core.errors import AppException, ErrorCode

ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hash password using Argon2id."""
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against Argon2id hash."""
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, Exception):
        return False


def create_access_token(
    user_id: UUID,
    email: str,
    role: str = "user",
    expires_delta: timedelta | None = None,
) -> str:
    """Generate a signed JWT access token (default 15 minutes)."""
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    encoded_jwt: str = jwt.encode(
        payload, settings.JWT_SECRET, algorithm="HS256"
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a signed JWT access token."""
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.JWT_SECRET, algorithms=["HS256"]
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        raise AppException(
            code=ErrorCode.TOKEN_EXPIRED,
            message="Access token has expired",
            status_code=401,
        ) from e
    except jwt.PyJWTError as e:
        raise AppException(
            code=ErrorCode.UNAUTHORIZED,
            message="Invalid authentication token",
            status_code=401,
        ) from e


def generate_refresh_token() -> str:
    """Generate a high-entropy cryptographically secure refresh token string."""
    return secrets.token_urlsafe(64)


def hash_token(token: str) -> str:
    """Compute SHA-256 hash of a token for indexing in the database."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
