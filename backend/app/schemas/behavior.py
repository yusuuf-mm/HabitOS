"""Behavior schemas."""
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, validator
from app.models.behavior import BehaviorCategory, TimeSlot


class ObjectiveImpactCreate(BaseModel):
    """Behavior impact creation schema."""

    objectiveId: UUID = Field(..., validation_alias="objectiveId")
    impactScore: float = Field(..., ge=-1.0, le=1.0, validation_alias="impactScore")


class ObjectiveImpactResponse(BaseModel):
    """Behavior impact response schema."""

    objectiveId: UUID = Field(..., validation_alias="objective_id", serialization_alias="objectiveId")
    objectiveName: str = Field(..., validation_alias="objective_name", serialization_alias="objectiveName")
    impactScore: float = Field(..., validation_alias="impact_score", serialization_alias="impactScore")

    class Config:
        from_attributes = True
        populate_by_name = True


class BehaviorCreate(BaseModel):
    """Create behavior request."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    category: BehaviorCategory = Field(...)
    energyCost: int = Field(..., ge=1, le=10, validation_alias="energyCost")
    durationMin: int = Field(..., gt=0, validation_alias="durationMin")
    durationMax: int = Field(..., gt=0, validation_alias="durationMax")
    preferredTimeSlots: List[TimeSlot] = Field(default_factory=lambda: [TimeSlot.FLEXIBLE], validation_alias="preferredTimeSlots")
    objectiveImpacts: List[ObjectiveImpactCreate] = Field(default_factory=list, validation_alias="objectiveImpacts")
    isActive: bool = Field(default=True, validation_alias="isActive")
    frequency: str = Field("daily")
    frequencyCount: Optional[int] = Field(None, validation_alias="frequencyCount")


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
    category: Optional[BehaviorCategory] = None
    energyCost: Optional[int] = Field(None, ge=1, le=10, validation_alias="energyCost")
    durationMin: Optional[int] = Field(None, gt=0, validation_alias="durationMin")
    durationMax: Optional[int] = Field(None, gt=0, validation_alias="durationMax")
    preferredTimeSlots: Optional[List[TimeSlot]] = Field(None, validation_alias="preferredTimeSlots")
    objectiveImpacts: Optional[List[ObjectiveImpactCreate]] = Field(None, validation_alias="objectiveImpacts")
    isActive: Optional[bool] = Field(None, validation_alias="isActive")
    frequency: Optional[str] = None
    frequencyCount: Optional[int] = Field(None, validation_alias="frequencyCount")


class BehaviorStatistics(BaseModel):
    """Behavior statistics."""

    total_completions: int = Field(0, serialization_alias="totalCompletions")
    avg_duration: Optional[float] = Field(None, serialization_alias="avgDuration")
    avg_satisfaction: Optional[float] = Field(None, serialization_alias="avgSatisfaction")
    last_completed: Optional[datetime] = Field(None, serialization_alias="lastCompleted")
    total_duration: int = Field(0, serialization_alias="totalDuration")

    class Config:
        populate_by_name = True


class BehaviorResponse(BaseModel):
    """Behavior response."""

    id: UUID
    user_id: UUID = Field(..., serialization_alias="userId")
    name: str
    description: Optional[str] = None
    category: BehaviorCategory
    energy_cost: int = Field(..., serialization_alias="energyCost")
    duration_min: int = Field(..., serialization_alias="durationMin")
    duration_max: int = Field(..., serialization_alias="durationMax")
    preferred_time_slots: List[TimeSlot] = Field(..., serialization_alias="preferredTimeSlots")
    objective_impacts: List[ObjectiveImpactResponse] = Field(default_factory=list, serialization_alias="objectiveImpacts")
    is_active: bool = Field(..., serialization_alias="isActive")
    frequency: str = Field(..., serialization_alias="frequency")
    frequency_count: Optional[int] = Field(None, serialization_alias="frequencyCount")
    created_at: datetime = Field(..., serialization_alias="createdAt")
    updated_at: datetime = Field(..., serialization_alias="updatedAt")
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
