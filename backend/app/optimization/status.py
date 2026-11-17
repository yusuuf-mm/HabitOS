"""Solver result contract and post-solve validation.

A plan may only be handed to the user when the solver reached optimality, or when
the solver reported a non-optimal status *and* this module validated the result:
integral values and every modelled constraint satisfied.
"""

from __future__ import annotations

from enum import Enum
from typing import List

from app.core.constants import MINUTES_PER_PERIOD, periods_for_time_slots
from app.optimization.models import OptimizationProblem, ScheduleItem

INTEGRAL_TOLERANCE = 1e-6


class SolveStatus(str, Enum):
    """Every terminal state of a solve."""

    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    PROTECTED_CONFLICT = "protected_conflict"
    UNBOUNDED = "unbounded"
    ERROR = "error"


def validate_schedule(
    problem: OptimizationProblem,
    items: List[ScheduleItem],
    tolerance: float = INTEGRAL_TOLERANCE,
) -> List[str]:
    """Return the list of violations in *items*. Empty list means valid."""
    violations: List[str] = []
    behaviors = {b.id: b for b in problem.behaviors}
    periods = problem.time_periods

    occupied: dict[int, str] = {}
    minutes_by_behavior: dict = {b.id: 0 for b in problem.behaviors}

    for item in items:
        behavior = behaviors.get(item.behavior_id)
        if behavior is None:
            violations.append(f"unknown behaviour {item.behavior_id}")
            continue

        duration = item.scheduled_duration
        if abs(duration - round(duration)) > tolerance:
            violations.append(f"{behavior.name}: fractional duration {duration}")
        if duration % MINUTES_PER_PERIOD != 0:
            violations.append(f"{behavior.name}: duration {duration} is not a multiple of {MINUTES_PER_PERIOD}")
        n_blocks = int(round(duration / MINUTES_PER_PERIOD))
        if n_blocks <= 0:
            violations.append(f"{behavior.name}: empty session")
            continue

        allowed = periods_for_time_slots(
            [s.value if hasattr(s, "value") else str(s) for s in behavior.preferred_time_slots]
        )
        for offset in range(n_blocks):
            period = item.time_period + offset
            if period < 0 or period >= periods:
                violations.append(f"{behavior.name}: period {period} outside the day")
                continue
            if period not in allowed:
                violations.append(f"{behavior.name}: period {period} outside its time windows")
            if period in occupied:
                violations.append(
                    f"period {period} used by both {occupied[period]} and {behavior.name}"
                )
            occupied[period] = behavior.name

        minutes_by_behavior[behavior.id] += duration

    for behavior in problem.behaviors:
        minutes = minutes_by_behavior[behavior.id]
        if minutes == 0:
            continue
        if minutes < behavior.min_duration:
            violations.append(f"{behavior.name}: {minutes} min below min_duration {behavior.min_duration}")
        if minutes > behavior.max_duration:
            violations.append(f"{behavior.name}: {minutes} min above max_duration {behavior.max_duration}")

    for constraint in problem.active_constraints:
        if constraint.type != "time_budget":
            continue
        limit = constraint.parameters.get("max_daily_minutes")
        if limit is None:
            continue
        scheduled = sum(minutes_by_behavior.values())
        if scheduled > limit:
            violations.append(f"{scheduled} min exceeds time budget {limit}")

    return violations


class InvalidSolutionError(Exception):
    """Raised when a non-optimal result fails validation."""

    def __init__(self, violations: List[str]):
        self.violations = violations
        super().__init__("; ".join(violations))
