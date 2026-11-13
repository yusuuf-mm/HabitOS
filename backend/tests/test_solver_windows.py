"""Solver-level checks: placements stay inside canonical time windows and after 05:00."""

from datetime import date
from uuid import uuid4

import pytest

from app.core.constants import MINUTES_PER_PERIOD, periods_for_time_slots
from app.optimization.models import BehaviorScheduleInput, OptimizationProblem
from app.optimization.solvers.linear import LinearSolver


def _problem(slots):
    behavior = BehaviorScheduleInput(
        id=uuid4(),
        name="Window Check",
        min_duration=30,
        typical_duration=30,
        max_duration=60,
        energy_cost=1.0,
        impacts={"health": 1.0},
        preferred_time_slots=slots,
    )
    return OptimizationProblem(
        user_id=uuid4(),
        behaviors=[behavior],
        objectives={"health": 1.0},
        constraints=[],
        start_date=date.today(),
        end_date=date.today(),
        time_periods=96,
    )


def _occupied_periods(solution):
    occupied = set()
    for item in solution.schedule_items:
        for block in range(item.scheduled_duration // MINUTES_PER_PERIOD):
            occupied.add(item.time_period + block)
    return occupied


@pytest.mark.parametrize("slots", [["morning"], ["evening", "night"]])
def test_no_placement_outside_selected_windows(slots):
    solution = LinearSolver(timeout_seconds=10).solve(_problem(slots), uuid4())
    occupied = _occupied_periods(solution)
    assert occupied, "solver produced no schedule"
    allowed = periods_for_time_slots(slots)
    assert occupied <= allowed


@pytest.mark.parametrize("slots", [["flexible"], ["early_morning"]])
def test_no_placement_before_0500(slots):
    solution = LinearSolver(timeout_seconds=10).solve(_problem(slots), uuid4())
    occupied = _occupied_periods(solution)
    assert occupied, "solver produced no schedule"
    # Period 20 == 05:00; canonical windows never start before 05:00.
    assert min(occupied) >= 20
