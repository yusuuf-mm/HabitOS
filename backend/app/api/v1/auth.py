"""Authentication routes."""
import logging
from datetime import timedelta, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, CurrentUserDep
from app.core import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
    AuthenticationError,
)
from app.models import User, Objective, ObjectiveType
from app.schemas import (
    UserRegistration,
    UserLogin,
    AuthResponse,
    TokenRefreshRequest,
    TokenRefreshResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=AuthResponse)
async def register(
    request: UserRegistration,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Register a new user."""
    # Check if user exists
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    if result.scalars().first():
        raise HTTPException(status_code=409, detail="Email already registered")

    # Create user
    user = User(
        email=request.email,
        username=request.username,
        password_hash=hash_password(request.password),
        first_name=request.first_name,
        last_name=request.last_name,
    )
    db.add(user)
    await db.flush()

    # Create default objectives
    default_weights = Objective.get_default_objectives()
    for obj_type, weight in default_weights.items():
        objective = Objective(
            user_id=user.id,
            type=obj_type,
            weight=weight,
        )
        db.add(objective)

    await db.commit()
    await db.refresh(user)

    # Generate tokens
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.id), "email": user.email}
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": UserResponse.from_orm(user),
    }


@router.post("/login", response_model=AuthResponse)
async def login(
    request: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Login user."""
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    user = result.scalars().first()

    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Update last login
    user.last_login = None  # Will use database default
    await db.commit()
    await db.refresh(user)

    # Generate tokens
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.id), "email": user.email}
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": UserResponse.from_orm(user),
    }


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_token(
    request: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Refresh access token."""
    try:
        payload = verify_token(request.refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }

@router.post("/logout")
async def logout(
    current_user: User = Depends(CurrentUserDep),
) -> dict:
    """Logout user."""
    # Since we use stateless JWT, we just return success
    # In a stateful system, we would invalidate the token here
    return {
        "success": True,
        "message": "Logged out successfully",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
