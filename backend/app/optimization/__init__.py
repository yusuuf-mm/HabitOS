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
from app.optimization.solvers.candidate import (
    MAX_BEHAVIORS,
    CandidateSolver,
)
from app.optimization.solvers.linear import LinearSolver
from app.optimization.status import INTEGRAL_TOLERANCE, SolveStatus, validate_schedule
from app.optimization.executor import run_in_solver_pool, shutdown_pool
from app.optimization.weights import normalise_weights, record_weights

__all__ = [
    "BehaviorScheduleInput",
    "ConstraintInput",
    "CandidateSolver",
    "MAX_BEHAVIORS",
    "INTEGRAL_TOLERANCE",
    "LinearSolver",
    "ObjectiveContribution",
    "ObjectiveInput",
    "OptimizationProblem",
    "OptimizationSolution",
    "ScheduleItem",
    "SolveStatus",
    "normalise_weights",
    "objective_contributions",
    "record_weights",
    "run_in_solver_pool",
    "shutdown_pool",
    "total_objective_value",
    "validate_schedule",
]
