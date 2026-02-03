"""User schemas."""
from typing import Optional
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, validator


class UserRegistration(BaseModel):
    """User registration request."""

    email: EmailStr
    name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8)

    @validator("password")
    def validate_password(cls, v):
        """Validate password strength."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLogin(BaseModel):
    """User login request."""

    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """User update request."""

    name: Optional[str] = Field(None, max_length=100)
    avatar: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)

    @validator("password")
    def validate_password(cls, v):
        """Validate password strength."""
        if v is None:
            return v
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v

class UserResponse(BaseModel):
    """User response."""

    id: UUID
    email: str
    name: str
    avatar: Optional[str] = None
    status: str
    createdAt: datetime = Field(..., validation_alias="created_at", serialization_alias="createdAt")
    updatedAt: datetime = Field(..., validation_alias="updated_at", serialization_alias="updatedAt")

    class Config:
        """Pydantic config."""

        from_attributes = True
        populate_by_name = True


class TokenRefreshRequest(BaseModel):
    """Token refresh request."""

    refreshToken: str = Field(..., validation_alias="refresh_token", serialization_alias="refreshToken")

    class Config:
        """Pydantic config."""
        
        populate_by_name = True


class TokenRefreshResponse(BaseModel):
    """Token refresh response."""

    accessToken: str = Field(..., validation_alias="access_token", serialization_alias="accessToken")
    tokenType: str = Field("bearer", validation_alias="token_type", serialization_alias="tokenType")


class AuthResponse(BaseModel):
    """Authentication response."""

    accessToken: str = Field(..., validation_alias="access_token", serialization_alias="accessToken")
    refreshToken: str = Field(..., validation_alias="refresh_token", serialization_alias="refreshToken")
    tokenType: str = Field("bearer", validation_alias="token_type", serialization_alias="tokenType")
    user: UserResponse
