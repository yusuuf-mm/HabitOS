"""Solver result contract: objective definition, validation, status, pooling."""

from app.optimization.models import (
    BehaviorScheduleInput,
    ConstraintInput,
    ObjectiveInput,
    ObjectiveContribution,
    OptimizationProblem,
    OptimizationSolution,
    ScheduleItem,
)
from app.optimization.objective import objective_contributions, total_objective_value
from app.optimization.solvers.linear import LinearSolver
from app.optimization.status import INTEGRAL_TOLERANCE, SolveStatus, validate_schedule
from app.optimization.executor import run_in_solver_pool, shutdown_pool

__all__ = [
    "BehaviorScheduleInput",
    "ConstraintInput",
    "INTEGRAL_TOLERANCE",
    "LinearSolver",
    "ObjectiveContribution",
    "ObjectiveInput",
    "OptimizationProblem",
    "OptimizationSolution",
    "ScheduleItem",
    "SolveStatus",
    "objective_contributions",
    "run_in_solver_pool",
    "shutdown_pool",
    "total_objective_value",
    "validate_schedule",
]
