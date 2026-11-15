"""The shipped formulation keeps the contract the block model promised.

These tests run against `CandidateSolver` — the model production now builds — and
assert the same user-facing promises the prototype's contract tests assert: one
contiguous session per behaviour, durations inside bounds, no overlaps, frozen
periods untouched, declines explained, one value definition, a hard cap.
"""

from datetime import date
from uuid import uuid4

import pytest

from app.core.constants import MINUTES_PER_PERIOD
from app.core.exceptions import InfeasibleProblemError, SolverError
from app.optimization import (
    MAX_BEHAVIORS,
    CandidateSolver,
    normalise_weights,
    record_weights,
)
from app.optimization.models import (
    BehaviorScheduleInput,
    OptimizationProblem,
)
from app.optimization.objective import total_objective_value
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


def _problem(behaviors, objectives=None, constraints=None) -> OptimizationProblem:
    return OptimizationProblem(
        user_id=uuid4(),
        behaviors=behaviors,
        objectives=objectives or {"health": 1.0},
        constraints=constraints or [],
        start_date=date.today(),
        end_date=date.today(),
        time_periods=96,
    )


def _cells(item):
    return set(range(item.time_period, item.time_period + item.scheduled_duration // MINUTES_PER_PERIOD))


def test_one_contiguous_session_per_behaviour():
    problem = _problem([_behavior()])
    solution = CandidateSolver(timeout_seconds=10).solve(problem, uuid4())

    assert solution.status == "optimal"
    assert solution.solver == "candidate"
    assert len(solution.schedule_items) == 1
    assert 30 <= solution.schedule_items[0].scheduled_duration <= 60
    assert solution.schedule_items[0].scheduled_duration % MINUTES_PER_PERIOD == 0
    assert validate_schedule(problem, solution.schedule_items) == []


def test_sessions_never_overlap():
    behaviors = [_behavior(f"B{i}", lo=30, hi=60) for i in range(6)]
    problem = _problem(behaviors)
    solution = CandidateSolver(timeout_seconds=10).solve(problem, uuid4())

    occupied = set()
    for item in solution.schedule_items:
        cells = _cells(item)
        assert not (cells & occupied), "two sessions share a period"
        occupied |= cells
    assert validate_schedule(problem, solution.schedule_items) == []


def test_frozen_periods_are_never_replanned():
    behavior = _behavior(lo=60, hi=60)
    problem = _problem([behavior])
    frozen = {0: {28: 1, 29: 1}}  # 30 minutes already elapsed
    solution = CandidateSolver(timeout_seconds=10).solve_partial_day(
        problem, uuid4(), frozen
    )

    assert solution.solver == "candidate_partial"
    assert solution.diagnostics["frozen_periods_count"] == 2

    # The elapsed half stays exactly where it was; the remaining 30 minutes are
    # planned somewhere else in the window, never over the frozen periods.
    frozen_items = [i for i in solution.schedule_items if i.time_period == 28]
    assert len(frozen_items) == 1 and frozen_items[0].scheduled_duration == 30
    planned = [i for i in solution.schedule_items if i.time_period != 28]
    assert planned, "the remaining minutes must still be planned"
    for item in planned:
        assert not (_cells(item) & set(frozen[0]))
    assert sum(i.scheduled_duration for i in solution.schedule_items) == 60
    assert validate_schedule(problem, solution.schedule_items) == []


def test_behaviour_with_no_room_is_declined_not_dropped():
    # Two hours of midday, all of it already elapsed: nothing is left to place,
    # and the behaviour is reported rather than silently dropped.
    behavior = _behavior(lo=60, hi=120, slots=("midday",))
    problem = _problem([behavior])
    frozen = {0: {t: 1 for t in range(48, 56)}}
    solution = CandidateSolver(timeout_seconds=10).solve_partial_day(
        problem, uuid4(), frozen
    )

    # Only the elapsed session is in the plan; nothing new was placed.
    assert [(i.time_period, i.scheduled_duration) for i in solution.schedule_items] == [(48, 120)]
    declared = {
        decline["behaviorId"]: decline["reason"]
        for decline in solution.diagnostics["declines"]
    }
    assert declared[str(behavior.id)] == "no_fit"
    assert validate_schedule(problem, solution.schedule_items) == []


def test_over_capacity_demand_is_reported_with_reasons():
    # Two hours of midday holds at most two 60-minute sessions.
    behaviors = [_behavior(f"B{i}", lo=60, hi=60, slots=("midday",)) for i in range(6)]
    problem = _problem(behaviors)
    solution = CandidateSolver(timeout_seconds=10).solve(problem, uuid4())

    assert solution.schedule_items, "some sessions still fit"
    declines = solution.diagnostics["declines"]
    assert declines, "the ones that do not fit must be reported"
    assert {d["reason"] for d in declines} == {"over_capacity"}
    assert len(solution.schedule_items) + len(declines) == len(behaviors)
    assert validate_schedule(problem, solution.schedule_items) == []


def test_objective_is_the_emitted_schedule_and_solver_objective_is_separate():
    behaviors = [_behavior(f"B{i}", lo=60, hi=60, slots=("midday",)) for i in range(6)]
    problem = _problem(behaviors)
    solution = CandidateSolver(timeout_seconds=10).solve(problem, uuid4())

    expected = total_objective_value(
        problem.objectives,
        {b.id: b for b in problem.behaviors},
        solution.schedule_items,
    )
    assert solution.total_objective_value == pytest.approx(expected)
    assert solution.diagnostics["declines"], "this instance must decline some behaviours"
    assert solution.diagnostics["solver_objective"] < solution.total_objective_value


def test_duration_options_keep_min_and_max_and_cap_their_count():
    from app.optimization.solvers.candidate import MAX_DURATION_OPTIONS, duration_options

    options = duration_options(15, 300)
    assert len(options) <= MAX_DURATION_OPTIONS
    assert options[0] * MINUTES_PER_PERIOD == 15
    assert options[-1] * MINUTES_PER_PERIOD == 300


def test_30_minute_sessions_start_on_the_half_hour():
    from app.optimization.solvers.candidate import contiguous_ranges, generate_candidates

    windows = contiguous_ranges(set(range(20, 96)))
    for start, length in generate_candidates(windows, 30, 30, earliest=20):
        assert length == 2
        assert start % 2 == 0, f"start {start} is not aligned to 30 minutes"


def test_plans_above_the_cap_are_refused_not_truncated():
    behaviors = [_behavior(f"B{i}") for i in range(MAX_BEHAVIORS + 1)]
    with pytest.raises(SolverError) as excinfo:
        CandidateSolver(timeout_seconds=10).solve(_problem(behaviors), uuid4())
    assert str(MAX_BEHAVIORS) in excinfo.value.detail


def test_forced_solve_places_the_requested_behaviour_and_names_the_cost():
    behaviors = [_behavior(f"B{i}", lo=60, hi=60, slots=("midday",)) for i in range(6)]
    requested = behaviors[-1]
    problem = _problem(behaviors)
    solver = CandidateSolver(timeout_seconds=10)

    baseline = solver.solve(problem, uuid4())
    forced = solver.solve_forced(problem, uuid4(), [requested.id])

    forced_items = [i for i in forced.schedule_items if i.behavior_id == requested.id]
    assert forced_items, "the requested behaviour must be in the forced plan"
    assert forced.solver == "candidate_forced"
    assert forced.diagnostics["forced_behavior_ids"] == [str(requested.id)]
    assert forced.total_objective_value <= baseline.total_objective_value
    assert all(
        d["reason"] in {"over_capacity", "no_fit", "preempted_by_protected"}
        for d in forced.diagnostics["declines"]
    )
    assert validate_schedule(problem, forced.schedule_items) == []


def test_force_is_impossible_without_a_window_long_enough():
    behavior = _behavior(lo=240, hi=240, slots=("midday",))  # 2h slot, 4h request
    problem = _problem([behavior])
    with pytest.raises(InfeasibleProblemError) as excinfo:
        CandidateSolver(timeout_seconds=10).solve_forced(problem, uuid4(), [behavior.id])
    assert "cannot be added" in excinfo.value.detail


def test_weights_are_normalised_and_recorded():
    assert sum(normalise_weights({"health": 3.0, "learning": 1.0}).values()) == pytest.approx(1.0)
    assert normalise_weights({"health": 3.0, "learning": 1.0})["health"] == pytest.approx(0.75)
    # All-zero weights still produce a distribution the solver can use.
    assert sum(normalise_weights({"health": 0.0, "learning": 0.0}).values()) == pytest.approx(1.0)

    record = record_weights({"health": 3.0, "learning": 1.0})
    assert record["raw"] == {"health": 3.0, "learning": 1.0}
    assert sum(record["normalised"].values()) == pytest.approx(1.0)


def test_plan_records_the_weights_it_used():
    problem = _problem([_behavior()])
    solution = CandidateSolver(timeout_seconds=10).solve(problem, uuid4())
    assert solution.diagnostics["objective_weights"] == {"health": 1.0}
    assert solution.diagnostics["formulation"] == "candidate"
