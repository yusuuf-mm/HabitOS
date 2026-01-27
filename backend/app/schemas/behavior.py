"""Behavior schemas."""
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, validator


class BehaviorImpacts(BaseModel):
    """Behavior impacts on objectives."""

    health: float = Field(0.0, ge=0.0, le=1.0)
    productivity: float = Field(0.0, ge=0.0, le=1.0)
    learning: float = Field(0.0, ge=0.0, le=1.0)
    wellness: float = Field(0.0, ge=0.0, le=1.0)
    social: float = Field(0.0, ge=0.0, le=1.0)


class BehaviorCreate(BaseModel):
    """Create behavior request."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    category: str = Field(...)
    min_duration: int = Field(..., gt=0)
    typical_duration: int = Field(..., gt=0)
    max_duration: int = Field(..., gt=0)
    energy_cost: float = Field(1.0, gt=0)
    preferred_time_slots: Optional[List[str]] = Field(default=["flexible"])
    impacts: BehaviorImpacts = Field(default_factory=BehaviorImpacts)

    @validator("category")
    def validate_category(cls, v):
        """Validate category."""
        valid = ["health", "productivity", "learning", "wellness", "social"]
        if v not in valid:
            raise ValueError(f"Category must be one of {valid}")
        return v

    @validator("typical_duration", always=True)
    def validate_durations(cls, v, values):
        """Validate duration relationships."""
        if "min_duration" in values and v < values["min_duration"]:
            raise ValueError("typical_duration must be >= min_duration")
        return v

    @validator("max_duration", always=True)
    def validate_max_duration(cls, v, values):
        """Validate max duration."""
        if "typical_duration" in values and v < values["typical_duration"]:
            raise ValueError("max_duration must be >= typical_duration")
        return v


class BehaviorUpdate(BaseModel):
    """Update behavior request."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = None
    min_duration: Optional[int] = Field(None, gt=0)
    typical_duration: Optional[int] = Field(None, gt=0)
    max_duration: Optional[int] = Field(None, gt=0)
    energy_cost: Optional[float] = Field(None, gt=0)
    preferred_time_slots: Optional[List[str]] = None
    impacts: Optional[BehaviorImpacts] = None


class BehaviorStatistics(BaseModel):
    """Behavior statistics."""

    total_completions: int = 0
    avg_duration: Optional[float] = None
    avg_satisfaction: Optional[float] = None
    last_completed: Optional[datetime] = None
    total_duration: int = 0


class BehaviorResponse(BaseModel):
    """Behavior response."""

    id: UUID
    name: str
    description: Optional[str]
    category: str
    min_duration: int
    typical_duration: int
    max_duration: int
    energy_cost: float
    is_active: bool
    preferred_time_slots: List[str]
    impacts: BehaviorImpacts
    created_at: datetime
    updated_at: datetime
    statistics: Optional[BehaviorStatistics] = None

    class Config:
        """Pydantic config."""

        from_attributes = True


class BehaviorListResponse(BaseModel):
    """Behavior list response."""

    total: int
    skip: int
    limit: int
    items: List[BehaviorResponse]
