"""Analytics schemas."""
from datetime import date
from typing import List, Literal

from pydantic import BaseModel


class DashboardStats(BaseModel):
    """Dashboard statistics."""

    total_behaviors: int
    active_behaviors: int
    total_optimization_runs: int
    completion_rate: float
    average_score: float
    streak_days: int


class DashboardSummary(BaseModel):
    """Dashboard summary."""

    stats: DashboardStats
    recent_optimizations: List["OptimizationSummary"]  # Forward ref to avoid circular import if needed
    recent_behaviors: List["BehaviorResponse"]
    today_schedule: List["ScheduledBehaviorResponse"]


class BehaviorCompletion(BaseModel):
    """Behavior completion data."""

    date: date
    completed: int
    scheduled: int


class ObjectiveProgress(BaseModel):
    """Objective progress data."""

    objective_name: str
    progress: float
    trend: Literal["up", "down", "stable"]


class CategoryDistribution(BaseModel):
    """Category distribution data."""

    category: str
    count: int
    percentage: float


class EnergyUsage(BaseModel):
    """Energy usage data."""

    date: date
    energy_spent: int
    energy_budget: int


class AnalyticsData(BaseModel):
    """Analytics data."""

    period: str
    behavior_completions: List[BehaviorCompletion]
    objective_progress: List[ObjectiveProgress]
    category_distribution: List[CategoryDistribution]
    energy_usage: List[EnergyUsage]


# Resolve forward references
from app.schemas.optimization import OptimizationSummary, ScheduledBehaviorResponse
from app.schemas.behavior import BehaviorResponse

DashboardSummary.update_forward_refs()
