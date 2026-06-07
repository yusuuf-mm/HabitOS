"""Security utilities for authentication and authorization."""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import bcrypt
from jwt import encode, decode, InvalidTokenError

from .config import settings


class TokenTypeError(InvalidTokenError):
    """Raised when a token's type claim does not match the expected type."""


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire, "type": "access"})

    encoded_jwt = encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    to_encode.update({"exp": expire, "type": "refresh"})

    encoded_jwt = encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def verify_token(token: str, expected_type: Optional[str] = None) -> Dict[str, Any]:
    """Verify JWT token and return payload.

    Args:
        token: Encoded JWT.
        expected_type: If provided, the token's ``type`` claim MUST match this
            value or a :class:`TokenTypeError` is raised. Pass ``"refresh"`` on
            the refresh endpoint so a stolen access token can't be used to mint
            new access tokens.
    """
    try:
        payload = decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except InvalidTokenError:
        raise InvalidTokenError("Invalid token")

    if expected_type is not None:
        token_type = payload.get("type")
        if token_type != expected_type:
            raise TokenTypeError(
                f"Invalid token type: expected '{expected_type}', got '{token_type}'"
            )

    return payload


def get_token_payload(token: str) -> Optional[Dict[str, Any]]:
    """Get token payload without raising exception."""
    try:
        return verify_token(token)
    except (InvalidTokenError, Exception):
        return None


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
