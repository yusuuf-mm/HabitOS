"""Optimization schemas."""
from typing import Optional, List, Dict, Any
from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field, validator


class ObjectiveContributionsResponse(BaseModel):
    """Objective contribution in result."""

    objective_type: str
    contribution: float
    weight: float


class ScheduledBehaviorResponse(BaseModel):
    """Scheduled behavior in result."""

    behavior_id: UUID
    behavior_name: str
    time_period: int
    scheduled_duration: int
    is_scheduled: bool = True


class InfeasibilityDiagnostics(BaseModel):
    """Infeasibility diagnostics."""

    reason: Optional[str] = None
    conflicting_constraints: Optional[List[str]] = None
    suggestions: Optional[List[str]] = None


class OptimizationRequest(BaseModel):
    """Optimization request."""

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    time_periods: Optional[int] = None

    @validator("start_date")
    def validate_dates(cls, v, values):
        """Validate date range."""
        if "end_date" in values and v > values["end_date"]:
            raise ValueError("start_date must be before end_date")
        return v


class OptimizationResult(BaseModel):
    """Optimization result."""

    optimization_run_id: UUID
    status: str
    solver: str
    total_objective_value: Optional[float]
    total_scheduled_duration: int
    scheduled_behavior_count: int
    execution_time_seconds: Optional[float]
    schedule_items: List[ScheduledBehaviorResponse]
    objective_contributions: Dict[str, ObjectiveContributionsResponse]
    diagnostics: Optional[Dict[str, Any]] = None

    class Config:
        """Pydantic config."""

        from_attributes = True


class OptimizationSummary(BaseModel):
    """Optimization run summary."""

    id: UUID
    status: str
    solver: str
    start_date: date
    end_date: date
    behaviors_scheduled: int
    total_scheduled_duration: int
    total_objective_value: Optional[float]
    execution_time_seconds: Optional[float]
    created_at: str

    class Config:
        """Pydantic config."""

        from_attributes = True


class OptimizationHistoryResponse(BaseModel):
    """Optimization history response."""

    total: int
    skip: int
    limit: int
    items: List[OptimizationSummary]
