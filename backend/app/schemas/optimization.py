"""Optimization schemas."""
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, validator
from .behavior import BehaviorResponse


class ObjectiveContributionSchema(BaseModel):
    """Objective contribution in result."""

    objectiveId: UUID
    objectiveName: str
    contribution: float
    percentage: float


class ScheduledBehaviorResponse(BaseModel):
    """Scheduled behavior in result."""

    id: UUID
    behaviorId: UUID
    behavior: BehaviorResponse
    scheduledDate: date
    timeSlot: str
    startTime: str  # HH:mm
    endTime: str    # HH:mm
    duration: int
    isCompleted: bool = False
    completedAt: Optional[datetime] = None


class OptimizationRequest(BaseModel):
    """Optimization request."""

    targetDate: Optional[date] = None
    includeInactiveBehaviors: bool = False
    maxExecutionTimeMs: int = 30000


class OptimizationRunResponse(BaseModel):
    """Optimization run response."""

    id: UUID
    userId: UUID = Field(..., validation_alias="user_id")
    status: str
    solverStatus: Optional[str] = Field(None, validation_alias="solver_status")
    scheduledBehaviors: List[ScheduledBehaviorResponse] = Field(default_factory=list, validation_alias="scheduled_behaviors")
    objectiveContributions: List[ObjectiveContributionSchema] = Field(default_factory=list, validation_alias="objective_contributions")
    totalScore: float = Field(0.0, validation_alias="total_score")
    executionTimeMs: int = Field(0, validation_alias="execution_time_ms")
    constraintsSatisfied: int = Field(0, validation_alias="constraints_satisfied")
    constraintsTotal: int = Field(0, validation_alias="constraints_total")
    createdAt: datetime = Field(..., validation_alias="created_at")
    completedAt: Optional[datetime] = Field(None, validation_alias="completed_at")

    class Config:
        from_attributes = True
        populate_by_name = True


class OptimizationResult(BaseModel):
    """Optimization result."""

    run: OptimizationRunResponse
    # schedule field is often used in frontend but might be derived or redundant with run.scheduledBehaviors
    # Keeping it as a placeholder if needed, but run is the main object.


class OptimizationHistoryResponse(BaseModel):
    """Optimization history response."""

    total: int
    skip: int
    limit: int
    data: List[OptimizationRunResponse]


class InfeasibilityDiagnostics(BaseModel):
    """Infeasibility diagnostics."""

    reason: Optional[str] = None
    conflictingConstraints: Optional[List[str]] = Field(None, validation_alias="conflicting_constraints")
    suggestions: Optional[List[str]] = None
