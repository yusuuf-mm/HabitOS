"""Optimization models and data classes."""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import date


@dataclass
class BehaviorScheduleInput:
    """Input behavior data for optimization."""

    id: UUID
    name: str
    min_duration: int
    typical_duration: int
    max_duration: int
    energy_cost: float
    impacts: Dict[str, float]
    preferred_time_slots: List[str] = field(default_factory=list)


@dataclass
class ObjectiveInput:
    """Input objective data for optimization."""

    type: str
    weight: float


@dataclass
class ConstraintInput:
    """Input constraint data for optimization."""

    type: str
    parameters: Dict[str, Any]
    is_active: bool = True


@dataclass
class OptimizationProblem:
    """Complete optimization problem specification."""

    user_id: UUID
    behaviors: List[BehaviorScheduleInput]
    objectives: Dict[str, float]  # {type: weight}
    constraints: List[ConstraintInput]
    start_date: date
    end_date: date
    time_periods: int

    def __post_init__(self):
        """Validate problem specification."""
        if not self.behaviors:
            raise ValueError("At least one behavior is required")
        if not self.objectives:
            raise ValueError("At least one objective is required")
        if self.start_date > self.end_date:
            raise ValueError("Start date must be before end date")
        if self.time_periods <= 0:
            raise ValueError("Time periods must be positive")

    @property
    def behavior_count(self) -> int:
        """Get number of behaviors."""
        return len(self.behaviors)

    @property
    def active_constraints(self) -> List[ConstraintInput]:
        """Get active constraints."""
        return [c for c in self.constraints if c.is_active]


@dataclass
class ScheduleItem:
    """Single scheduled behavior."""

    behavior_id: UUID
    behavior_name: str
    time_period: int
    scheduled_duration: int
    is_scheduled: bool = True


@dataclass
class ObjectiveContribution:
    """Contribution to objective value."""

    objective_type: str
    contribution: float
    weight: float


@dataclass
class OptimizationSolution:
    """Complete optimization solution."""

    optimization_run_id: UUID
    status: str  # "optimal", "feasible", "infeasible", "unbounded"
    solver: str
    total_objective_value: Optional[float]
    schedule_items: List[ScheduleItem]
    objective_contributions: Dict[str, ObjectiveContribution]
    execution_time_seconds: Optional[float] = None
    diagnostics: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Validate solution."""
        if self.status not in ["optimal", "feasible", "infeasible", "unbounded"]:
            raise ValueError(f"Invalid status: {self.status}")

    @property
    def total_scheduled_duration(self) -> int:
        """Get total scheduled duration."""
        return sum(item.scheduled_duration for item in self.schedule_items if item.is_scheduled)

    @property
    def scheduled_behavior_count(self) -> int:
        """Get number of scheduled behaviors."""
        return sum(1 for item in self.schedule_items if item.is_scheduled)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "optimization_run_id": str(self.optimization_run_id),
            "status": self.status,
            "solver": self.solver,
            "total_objective_value": self.total_objective_value,
            "total_scheduled_duration": self.total_scheduled_duration,
            "scheduled_behavior_count": self.scheduled_behavior_count,
            "execution_time_seconds": self.execution_time_seconds,
            "schedule_items": [
                {
                    "behavior_id": str(item.behavior_id),
                    "behavior_name": item.behavior_name,
                    "time_period": item.time_period,
                    "scheduled_duration": item.scheduled_duration,
                    "is_scheduled": item.is_scheduled,
                }
                for item in self.schedule_items
            ],
            "objective_contributions": {
                obj_type: {
                    "contribution": contrib.contribution,
                    "weight": contrib.weight,
                }
                for obj_type, contrib in self.objective_contributions.items()
            },
            "diagnostics": self.diagnostics,
        }
