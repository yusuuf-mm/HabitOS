"""Tracking schemas."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CompletionLogBase(BaseModel):
    """Base schema for completion logs."""

    behavior_id: UUID
    optimization_run_id: Optional[UUID] = None
    actual_duration: int = Field(..., gt=0)
    completed_at: datetime
    satisfaction_score: Optional[int] = Field(None, ge=1, le=5)
    notes: Optional[str] = None
    context: Optional[dict] = None


class CompletionLogCreate(CompletionLogBase):
    """Create completion log request."""

    pass


class CompletionLogUpdate(BaseModel):
    """Update completion log request."""

    actual_duration: Optional[int] = Field(None, gt=0)
    completed_at: Optional[datetime] = None
    satisfaction_score: Optional[int] = Field(None, ge=1, le=5)
    notes: Optional[str] = None
    context: Optional[dict] = None


class CompletionLogResponse(CompletionLogBase):
    """Completion log response."""

    id: UUID
    user_id: UUID
    created_at: datetime

    class Config:
        """Pydantic config."""

        from_attributes = True
