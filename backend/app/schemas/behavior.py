"""Behavior schemas."""
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, validator


class ObjectiveImpactCreate(BaseModel):
    """Behavior impact creation schema."""

    objectiveId: UUID = Field(..., validation_alias="objectiveId")
    impactScore: float = Field(..., ge=-1.0, le=1.0, validation_alias="impactScore")


class ObjectiveImpactResponse(BaseModel):
    """Behavior impact response schema."""

    objectiveId: UUID
    objectiveName: str
    impactScore: float

    class Config:
        from_attributes = True


class BehaviorCreate(BaseModel):
    """Create behavior request."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    category: str = Field(...)
    energyCost: int = Field(..., ge=1, le=10, validation_alias="energyCost")
    durationMin: int = Field(..., gt=0, validation_alias="durationMin")
    durationMax: int = Field(..., gt=0, validation_alias="durationMax")
    preferredTimeSlots: List[str] = Field(default_factory=lambda: ["flexible"], validation_alias="preferredTimeSlots")
    objectiveImpacts: List[ObjectiveImpactCreate] = Field(default_factory=list, validation_alias="objectiveImpacts")
    isActive: bool = Field(default=True, validation_alias="isActive")
    frequency: str = Field("daily")
    frequencyCount: Optional[int] = Field(None, validation_alias="frequencyCount")

    @validator("category")
    def validate_category(cls, v):
        """Validate category."""
        valid = [
            "health",
            "productivity",
            "learning",
            "social",
            "financial",
            "creativity",
            "mindfulness",
            "wellness",
        ]
        if v not in valid:
            raise ValueError(f"Category must be one of {valid}")
        return v

    @validator("durationMax", always=True)
    def validate_durations(cls, v, values):
        """Validate duration relationships."""
        if "durationMin" in values and v < values["durationMin"]:
            raise ValueError("durationMax must be >= durationMin")
        return v


class BehaviorUpdate(BaseModel):
    """Update behavior request."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = None
    energyCost: Optional[int] = Field(None, ge=1, le=10, validation_alias="energyCost")
    durationMin: Optional[int] = Field(None, gt=0, validation_alias="durationMin")
    durationMax: Optional[int] = Field(None, gt=0, validation_alias="durationMax")
    preferredTimeSlots: Optional[List[str]] = Field(None, validation_alias="preferredTimeSlots")
    objectiveImpacts: Optional[List[ObjectiveImpactCreate]] = Field(None, validation_alias="objectiveImpacts")
    isActive: Optional[bool] = Field(None, validation_alias="isActive")
    frequency: Optional[str] = None
    frequencyCount: Optional[int] = Field(None, validation_alias="frequencyCount")


class BehaviorStatistics(BaseModel):
    """Behavior statistics."""

    totalCompletions: int = Field(0, validation_alias="total_completions")
    avgDuration: Optional[float] = Field(None, validation_alias="avg_duration")
    avgSatisfaction: Optional[float] = Field(None, validation_alias="avg_satisfaction")
    lastCompleted: Optional[datetime] = Field(None, validation_alias="last_completed")
    totalDuration: int = Field(0, validation_alias="total_duration")

    class Config:
        populate_by_name = True


class BehaviorResponse(BaseModel):
    """Behavior response."""

    id: UUID
    userId: UUID = Field(..., validation_alias="user_id")
    name: str
    description: Optional[str] = None
    category: str
    energyCost: int = Field(..., validation_alias="energy_cost")
    durationMin: int = Field(..., validation_alias="duration_min")
    durationMax: int = Field(..., validation_alias="duration_max")
    preferredTimeSlots: List[str] = Field(..., validation_alias="preferred_time_slots")
    objectiveImpacts: List[ObjectiveImpactResponse] = Field(default_factory=list, validation_alias="objective_impacts")
    isActive: bool = Field(..., validation_alias="is_active")
    frequency: str
    frequencyCount: Optional[int] = Field(None, validation_alias="frequency_count")
    createdAt: datetime = Field(..., validation_alias="created_at")
    updatedAt: datetime = Field(..., validation_alias="updated_at")
    statistics: Optional[BehaviorStatistics] = None

    class Config:
        """Pydantic config."""

        from_attributes = True
        populate_by_name = True


class BehaviorListResponse(BaseModel):
    """Behavior list response."""

    total: int
    skip: int
    limit: int
    data: List[BehaviorResponse]
