"""Analytics schemas."""
from datetime import date, datetime
from typing import List, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DashboardStats(BaseModel):
    """Dashboard statistics."""

    totalBehaviors: int = Field(..., validation_alias="total_behaviors", serialization_alias="totalBehaviors")
    activeBehaviors: int = Field(..., validation_alias="active_behaviors", serialization_alias="activeBehaviors")
    totalOptimizationRuns: int = Field(..., validation_alias="total_optimization_runs", serialization_alias="totalOptimizationRuns")
    completionRate: float = Field(..., validation_alias="completion_rate", serialization_alias="completionRate")
    averageScore: float = Field(..., validation_alias="average_score", serialization_alias="averageScore")
    streakDays: int = Field(..., validation_alias="streak_days", serialization_alias="streakDays")

    class Config:
        populate_by_name = True


class DashboardScheduledBehavior(BaseModel):
    """Scheduled behavior for dashboard summary."""

    id: UUID
    behavior_name: str = Field(..., serialization_alias="behaviorName")
    time_slot: str = Field(..., serialization_alias="timeSlot")
    start_time: str = Field(..., serialization_alias="startTime")
    is_completed: bool = Field(..., serialization_alias="isCompleted")

    class Config:
        populate_by_name = True


class DashboardBehavior(BaseModel):
    """Behavior for dashboard summary."""

    id: UUID
    name: str
    category: str
    is_active: bool = Field(..., serialization_alias="isActive")
    created_at: datetime = Field(..., serialization_alias="createdAt")

    class Config:
        populate_by_name = True


class DashboardSummary(BaseModel):
    """Dashboard summary."""

    stats: DashboardStats
    recentOptimizations: List["OptimizationSummary"] = Field(..., validation_alias="recent_optimizations", serialization_alias="recentOptimizations")
    recentBehaviors: List[DashboardBehavior] = Field(..., validation_alias="recent_behaviors", serialization_alias="recentBehaviors")
    todaySchedule: List[DashboardScheduledBehavior] = Field(..., validation_alias="today_schedule", serialization_alias="todaySchedule")

    class Config:
        populate_by_name = True


class BehaviorCompletion(BaseModel):
    """Behavior completion data."""

    date: date
    completed: int
    scheduled: int


class ObjectiveProgress(BaseModel):
    """Objective progress data."""

    objectiveName: str = Field(..., validation_alias="objective_name", serialization_alias="objectiveName")
    progress: float
    trend: Literal["up", "down", "stable"]

    class Config:
        populate_by_name = True


class CategoryDistribution(BaseModel):
    """Category distribution data."""

    category: str
    count: int
    percentage: float


class EnergyUsage(BaseModel):
    """Energy usage data."""

    date: date
    energySpent: int = Field(..., validation_alias="energy_spent", serialization_alias="energySpent")
    energyBudget: int = Field(..., validation_alias="energy_budget", serialization_alias="energyBudget")

    class Config:
        populate_by_name = True


class AnalyticsData(BaseModel):
    """Analytics data."""

    period: str
    behaviorCompletions: List[BehaviorCompletion] = Field(..., validation_alias="behavior_completions", serialization_alias="behaviorCompletions")
    objectiveProgress: List[ObjectiveProgress] = Field(..., validation_alias="objective_progress", serialization_alias="objectiveProgress")
    categoryDistribution: List[CategoryDistribution] = Field(..., validation_alias="category_distribution", serialization_alias="categoryDistribution")
    energyUsage: List[EnergyUsage] = Field(..., validation_alias="energy_usage", serialization_alias="energyUsage")

    class Config:
        populate_by_name = True


# Resolve forward references
from app.schemas.optimization import OptimizationSummary, ScheduledBehaviorResponse
from app.schemas.behavior import BehaviorResponse

DashboardSummary.update_forward_refs()
