"""The single definition of the objective value.

Every code path that reports an objective value must go through this module.
It is computed from the *final schedule* (behaviour x minutes), never from the
solver's internal LP objective, so a full solve, a partial re-solve and a forced
solve agree for the same schedule.

Units: weighted impact points x minutes. No scaling is applied.
"""

from __future__ import annotations

from typing import Dict, Mapping, Sequence
from uuid import UUID

from app.optimization.models import BehaviorScheduleInput, ObjectiveContribution, ScheduleItem


def _impact_of(
    objectives: Mapping[str, float],
    behavior: BehaviorScheduleInput,
) -> float:
    """Weighted impact per scheduled minute for one behaviour."""
    return sum(
        weight * behavior.impacts.get(objective_type, 0.0)
        for objective_type, weight in objectives.items()
    )


def total_objective_value(
    objectives: Mapping[str, float],
    behaviors: Mapping[UUID, BehaviorScheduleInput],
    items: Sequence[ScheduleItem],
) -> float:
    """Total objective value of a schedule: sum over scheduled minutes."""
    total = 0.0
    for item in items:
        if not item.is_scheduled:
            continue
        behavior = behaviors.get(item.behavior_id)
        if behavior is None:
            continue
        total += _impact_of(objectives, behavior) * item.scheduled_duration
    return round(total, 4)


def objective_contributions(
    objectives: Mapping[str, float],
    behaviors: Mapping[UUID, BehaviorScheduleInput],
    items: Sequence[ScheduleItem],
) -> Dict[str, ObjectiveContribution]:
    """Per-objective contributions. Their sum equals :func:`total_objective_value`."""
    minutes_by_objective: Dict[str, float] = {key: 0.0 for key in objectives}
    for item in items:
        if not item.is_scheduled:
            continue
        behavior = behaviors.get(item.behavior_id)
        if behavior is None:
            continue
        for objective_type in objectives:
            minutes_by_objective[objective_type] += (
                behavior.impacts.get(objective_type, 0.0) * item.scheduled_duration
            )

    return {
        objective_type: ObjectiveContribution(
            objective_type=objective_type,
            contribution=round(minutes_by_objective[objective_type] * weight, 4),
            weight=weight,
        )
        for objective_type, weight in objectives.items()
    }
