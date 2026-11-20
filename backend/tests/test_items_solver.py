"""Commitments as blocked periods through CandidateSolver (part C unit tests).

Blocked periods are occupied time, not choices: candidates touching them are
never created, and whatever cannot fit is declined with a reason.
"""

import dataclasses
from datetime import date
from uuid import uuid4

from app.optimization import CandidateSolver
from app.optimization.models import (
    BehaviorScheduleInput,
    OptimizationProblem,
)
from app.optimization.status import validate_schedule


def _behavior(
    name="Run",
    *,
    lo=30,
    hi=60,
    slots=("morning",),
    impacts=None,
) -> BehaviorScheduleInput:
    return BehaviorScheduleInput(
        id=uuid4(),
        name=name,
        min_duration=lo,
        typical_duration=lo,
        max_duration=hi,
        energy_cost=1.0,
        impacts=impacts or {"health": 1.0},
        preferred_time_slots=list(slots),
    )


def _problem(behaviors, blocked=frozenset()) -> OptimizationProblem:
    return OptimizationProblem(
        user_id=uuid4(),
        behaviors=behaviors,
        objectives={"health": 1.0},
        constraints=[],
        start_date=date.today(),
        end_date=date.today(),
        time_periods=96,
        blocked_periods=blocked,
    )


def test_commitment_covering_the_only_window_declines_with_reason():
    # Midday is periods 48..56; blocking all of it leaves a midday-only
    # behaviour with no candidate, so it is declined as "no_fit", not dropped.
    behavior = _behavior(lo=60, hi=60, slots=("midday",))
    problem = _problem([behavior], blocked=frozenset(range(48, 56)))
    solution = CandidateSolver(timeout_seconds=10).solve(problem, uuid4())

    declared = {
        decline["behaviorId"]: decline["reason"]
        for decline in solution.diagnostics["declines"]
    }
    assert declared[str(behavior.id)] == "no_fit"
    assert not [
        item for item in solution.schedule_items if item.behavior_id == behavior.id
    ]


def test_blocked_periods_outside_the_window_change_nothing_but_are_reported():
    # Periods 72..80 (evening) do not touch the morning window, so the session
    # is still placed; the block is only reported in diagnostics.
    behavior = _behavior(lo=30, hi=30, slots=("morning",))
    problem = _problem([behavior], blocked=frozenset(range(72, 80)))
    solution = CandidateSolver(timeout_seconds=10).solve(problem, uuid4())

    assert solution.schedule_items, "the session must still be placed"
    assert solution.diagnostics["blocked_periods_count"] == 8
    assert validate_schedule(problem, solution.schedule_items) == []


def test_commitment_during_a_replan_and_inside_frozen_periods():
    # Morning behaviour, 60 minutes, with 30 already elapsed (periods 28, 29).
    behavior = _behavior(lo=60, hi=60, slots=("morning",))
    problem = _problem([behavior])
    frozen = {0: {28: 1, 29: 1}}
    solver = CandidateSolver(timeout_seconds=10)

    # (i) A block inside the frozen periods changes nothing: the frozen run is
    # re-emitted at period 28 and the remaining minutes are still placed.
    inside = dataclasses.replace(problem, blocked_periods=frozenset({28, 29}))
    solution = solver.solve_partial_day(inside, uuid4(), frozen)

    frozen_items = [i for i in solution.schedule_items if i.time_period == 28]
    assert len(frozen_items) == 1
    assert frozen_items[0].scheduled_duration == 30
    assert sum(i.scheduled_duration for i in solution.schedule_items) == 60
    assert validate_schedule(inside, solution.schedule_items) == []

    # (ii) A block covering the rest of the reachable morning (periods 32..48)
    # must not crash; whatever remains must still be valid.
    covered = dataclasses.replace(problem, blocked_periods=frozenset(range(32, 48)))
    replanned = solver.solve_partial_day(covered, uuid4(), frozen)
    assert validate_schedule(covered, replanned.schedule_items) == []


def test_zero_blocked_periods_matches_unblocked_solve():
    # Empty blocked_periods is today's behaviour: identical plan, only the
    # timing differs.
    run_id = uuid4()
    behaviors = [_behavior("A", lo=30, hi=60), _behavior("B", lo=30, hi=30)]
    problem = _problem(behaviors)
    explicit = dataclasses.replace(problem, blocked_periods=frozenset())

    solver = CandidateSolver(timeout_seconds=10)
    baseline = solver.solve(problem, run_id).to_dict()
    other = solver.solve(explicit, run_id).to_dict()
    baseline.pop("execution_time_seconds")
    other.pop("execution_time_seconds")
    assert baseline == other
