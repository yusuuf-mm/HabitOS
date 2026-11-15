"""Optimization schemas."""
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, validator
from .behavior import BehaviorResponse


class ObjectiveContributionSchema(BaseModel):
    """Objective contribution in result."""

    objectiveId: UUID = Field(..., validation_alias="objective_id", serialization_alias="objectiveId")
    objectiveName: str = Field(..., validation_alias="objective_name", serialization_alias="objectiveName")
    contribution: float
    percentage: float

    class Config:
        populate_by_name = True


class ScheduledBehaviorResponse(BaseModel):
    """Scheduled behavior in result."""

    id: UUID
    behaviorId: UUID = Field(..., validation_alias="behavior_id", serialization_alias="behaviorId")
    behavior: BehaviorResponse
    scheduledDate: date = Field(..., validation_alias="scheduled_date", serialization_alias="scheduledDate")
    timeSlot: str = Field(..., validation_alias="time_slot", serialization_alias="timeSlot")
    startTime: str = Field(..., validation_alias="start_time", serialization_alias="startTime")  # HH:mm
    endTime: str = Field(..., validation_alias="end_time", serialization_alias="endTime")    # HH:mm
    duration: int
    isCompleted: bool = Field(False, validation_alias="is_completed", serialization_alias="isCompleted")
    completedAt: Optional[datetime] = Field(None, validation_alias="completed_at", serialization_alias="completedAt")

    class Config:
        populate_by_name = True
        from_attributes = True


class OptimizationSummary(BaseModel):
    """Brief summary of an optimization run."""

    id: UUID
    status: str
    score: float
    createdAt: datetime = Field(..., validation_alias="created_at", serialization_alias="createdAt")

    class Config:
        populate_by_name = True
        from_attributes = True


class OptimizationRequest(BaseModel):
    """Optimization request."""

    targetDate: Optional[date] = None
    includeInactiveBehaviors: bool = False
    maxExecutionTimeMs: int = 30000


class OptimizationRunResponse(BaseModel):
    """Optimization run response."""

    id: UUID
    userId: UUID = Field(..., validation_alias="user_id", serialization_alias="userId")
    status: str
    solverStatus: Optional[str] = Field(None, validation_alias="solver_status", serialization_alias="solverStatus")
    scheduledBehaviors: List[ScheduledBehaviorResponse] = Field(default_factory=list, validation_alias="scheduled_behaviors", serialization_alias="scheduledBehaviors")
    objectiveContributions: List[ObjectiveContributionSchema] = Field(default_factory=list, validation_alias="objective_contributions", serialization_alias="objectiveContributions")
    totalScore: float = Field(0.0, validation_alias="total_score", serialization_alias="totalScore")
    executionTimeMs: int = Field(0, validation_alias="execution_time_ms", serialization_alias="executionTimeMs")
    constraintsSatisfied: int = Field(0, validation_alias="constraints_satisfied", serialization_alias="constraintsSatisfied")
    constraintsTotal: int = Field(0, validation_alias="constraints_total", serialization_alias="constraintsTotal")
    createdAt: datetime = Field(..., validation_alias="created_at", serialization_alias="createdAt")
    completedAt: Optional[datetime] = Field(None, validation_alias="completed_at", serialization_alias="completedAt")

    class Config:
        from_attributes = True
        populate_by_name = True


class OptimizationResult(BaseModel):
    """Optimization result."""

    run: OptimizationRunResponse
    schedule: Optional["DailySchedule"] = None


class OptimizationHistoryResponse(BaseModel):
    """Optimization history response."""

    total: int
    skip: int
    limit: int
    data: List[OptimizationRunResponse]


from .schedule import DailySchedule
OptimizationResult.update_forward_refs()


class ForcedIncludeRequest(BaseModel):
    """Which behaviours to force into the day."""

    targetDate: Optional[date] = None
    behaviorIds: List[UUID] = Field(default_factory=list)


class ForcedSession(BaseModel):
    """A session the forced-include solve placed."""

    behaviorId: UUID
    behaviorName: str
    startTime: str
    endTime: str
    duration: int


class DisplacedSession(BaseModel):
    """A session that had to give way to fit the requested behaviours."""

    behaviorId: UUID
    behaviorName: str
    reason: str
    minutes: int


class ForcedIncludeResult(BaseModel):
    """The cost of fitting the requested behaviours into the day."""

    fits: bool
    forced: List[ForcedSession] = Field(default_factory=list)
    displaced: List[DisplacedSession] = Field(default_factory=list)
    relaxations: List[Dict[str, Any]] = Field(default_factory=list)
    objectiveChange: float = 0.0
    solverObjective: Optional[float] = None
    seconds: float = 0.0
    reason: Optional[str] = None


class InfeasibilityDiagnostics(BaseModel):
    """Infeasibility diagnostics."""

    reason: Optional[str] = None
    conflictingConstraints: Optional[List[str]] = Field(None, validation_alias="conflicting_constraints", serialization_alias="conflictingConstraints")
    suggestions: Optional[List[str]] = None

    class Config:
        populate_by_name = True
