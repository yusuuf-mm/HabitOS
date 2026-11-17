"""Solver contract: one objective definition, validated results, no relaxations."""

from datetime import date
from uuid import uuid4

import pytest
from pulp import LpStatus, PULP_CBC_CMD

from app.core.exceptions import SolverError, SolverTimeoutError
from app.optimization.models import (
    BehaviorScheduleInput,
    ConstraintInput,
    OptimizationProblem,
    ScheduleItem,
)
from app.optimization.objective import objective_contributions, total_objective_value
from app.optimization.solvers.linear import LinearSolver
from app.optimization.status import validate_schedule


def _behaviour(name: str, slots: list[str], min_d: int, max_d: int, impacts: dict) -> BehaviorScheduleInput:
    return BehaviorScheduleInput(
        id=uuid4(),
        name=name,
        min_duration=min_d,
        typical_duration=min_d,
        max_duration=max_d,
        energy_cost=1.0,
        impacts=impacts,
        preferred_time_slots=slots,
    )


def _problem(behaviours, objectives=None, constraints=None) -> OptimizationProblem:
    return OptimizationProblem(
        user_id=uuid4(),
        behaviors=behaviours,
        objectives=objectives or {"health": 0.6, "productivity": 0.4},
        constraints=constraints or [],
        start_date=date.today(),
        end_date=date.today(),
        time_periods=96,
    )


def _two_behaviours():
    return [
        _behaviour("Run", ["morning"], 30, 60, {"health": 0.9, "productivity": 0.1}),
        _behaviour("Write", ["evening"], 30, 60, {"health": 0.2, "productivity": 0.8}),
    ]


def test_full_and_partial_solve_report_the_same_objective():
    """The two solve paths must agree: no hidden scaling in either."""
    problem = _problem(_two_behaviours())
    solver = LinearSolver(timeout_seconds=10)

    full = solver.solve(problem, uuid4())
    partial = solver.solve_partial_day(problem, uuid4(), {})

    assert full.status == "optimal"
    assert partial.status == "optimal"
    assert full.total_objective_value == pytest.approx(partial.total_objective_value)
    assert full.total_objective_value > 0


def test_objective_value_matches_the_schedule_it_reports():
    """Total value is a function of the schedule, not of the LP objective."""
    problem = _problem(_two_behaviours())
    solution = LinearSolver(timeout_seconds=10).solve(problem, uuid4())
    behaviors = {b.id: b for b in problem.behaviors}

    recomputed = total_objective_value(problem.objectives, behaviors, solution.schedule_items)
    assert solution.total_objective_value == pytest.approx(recomputed)

    contributions = objective_contributions(problem.objectives, behaviors, solution.schedule_items)
    assert sum(c.contribution for c in contributions.values()) == pytest.approx(
        solution.total_objective_value, abs=1e-6
    )


def test_objective_units_are_minutes_not_periods():
    """A 60-minute session is worth 60 minutes of impact, not 4 periods of it."""
    behaviour = _behaviour("Run", ["morning"], 60, 60, {"health": 1.0})
    problem = _problem([behaviour], objectives={"health": 1.0})
    solution = LinearSolver(timeout_seconds=10).solve(problem, uuid4())

    assert solution.total_objective_value == pytest.approx(60.0)
    # The block model has no contiguity constraint, so CBC may split these 60
    # minutes into several sessions depending on the build. Only the total is
    # contractual until Phase 3 replaces the formulation.
    assert sum(item.scheduled_duration for item in solution.schedule_items) == 60


class _NotSolvedSolver(LinearSolver):
    """Emulates CBC hitting its limit and leaving relaxation values behind."""

    def _run_solver(self, lp):
        lp.solve(PULP_CBC_CMD(timeLimit=10, msg=0))
        for variable in lp.variables():
            variable.varValue = 0.4
        lp.status = 0  # pulp LpStatusNotSolved (0); -1 would mean infeasible
        return LpStatus[lp.status]


def test_not_solved_never_becomes_a_plan():
    problem = _problem(_two_behaviours())
    with pytest.raises(SolverTimeoutError):
        _NotSolvedSolver(timeout_seconds=1).solve(problem, uuid4())


def test_not_solved_with_acceptance_still_needs_integral_values():
    """Even when non-optimal results are accepted, a relaxation is rejected."""
    problem = _problem(_two_behaviours())
    with pytest.raises(SolverError):
        _NotSolvedSolver(timeout_seconds=1, accept_nonoptimal=True).solve(problem, uuid4())


def test_validation_rejects_overlaps_and_out_of_window_sessions():
    behaviours = _two_behaviours()
    run, write = behaviours
    problem = _problem(behaviours)

    overlapping = [
        ScheduleItem(run.id, run.name, 40, 30),
        ScheduleItem(write.id, write.name, 40, 30),
    ]
    assert any("used by both" in v for v in validate_schedule(problem, overlapping))

    out_of_window = [ScheduleItem(write.id, write.name, 10, 30)]  # 02:30, outside 17:00-21:00
    assert any("outside its time windows" in v for v in validate_schedule(problem, out_of_window))

    too_short = [ScheduleItem(run.id, run.name, 60, 15)]
    assert any("below min_duration" in v for v in validate_schedule(problem, too_short))


def test_validation_accepts_a_valid_schedule():
    run = _behaviour("Run", ["morning"], 30, 60, {"health": 1.0})
    problem = _problem([run], objectives={"health": 1.0})
    assert validate_schedule(problem, [ScheduleItem(run.id, run.name, 40, 30)]) == []


def test_time_budget_is_checked_by_validation():
    run = _behaviour("Run", ["morning"], 30, 120, {"health": 1.0})
    problem = _problem(
        [run],
        objectives={"health": 1.0},
        constraints=[ConstraintInput(type="time_budget", parameters={"max_daily_minutes": 45})],
    )
    violations = validate_schedule(problem, [ScheduleItem(run.id, run.name, 40, 60)])
    assert any("time budget" in v for v in violations)


def test_infeasible_problem_raises_instead_of_returning_a_plan():
    # 20 behaviours x 60 min into a single 60-minute window cannot fit.
    behaviours = [
        _behaviour(f"B{i}", ["midday"], 60, 60, {"health": 1.0}) for i in range(20)
    ]
    problem = _problem(behaviours, objectives={"health": 1.0})
    with pytest.raises(Exception) as excinfo:
        LinearSolver(timeout_seconds=10).solve(problem, uuid4())
    assert excinfo.type.__name__ == "InfeasibleProblemError"
