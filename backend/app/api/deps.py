"""Dependency injection utilities."""
import logging
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core import verify_token, AuthenticationError, settings
from app.db.database import get_db as get_db_session
from app.models import User

logger = logging.getLogger(__name__)

security = HTTPBearer()

# Type aliases for dependency injection
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_user(
    db: AsyncSession = Depends(get_db_session),
    credentials = Depends(security),
) -> User:
    """Get current authenticated user."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = verify_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current active user."""
    if current_user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active",
        )
    return current_user


async def get_optional_user(
    db: AsyncSession = Depends(get_db_session),
    credentials = Depends(security),
) -> Optional[User]:
    """Get current user if authenticated, None otherwise."""
    if not credentials:
        return None

    try:
        payload = verify_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
    except Exception:
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalars().first()


# Re-export for convenience
CurrentUserDep = Annotated[User, Depends(get_current_active_user)]
OptionalUserDep = Annotated[Optional[User], Depends(get_optional_user)]


def get_db() -> AsyncSession:
    """Get database session (compatibility wrapper)."""
    return Depends(get_db_session)
