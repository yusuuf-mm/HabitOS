"""Linear programming solver for behavior optimization."""
import logging
from typing import Dict, List, Optional, Any
from uuid import UUID
from datetime import date

from pulp import (
    LpMaximize,
    LpProblem,
    LpVariable,
    lpSum,
    PULP_CBC_CMD,
    LpStatus,
)

from app.core.exceptions import (
    InfeasibleProblemError,
    UnboundedProblemError,
    SolverTimeoutError,
    SolverError,
)
from app.optimization.models import (
    OptimizationProblem,
    OptimizationSolution,
    ScheduleItem,
    ObjectiveContribution,
)

logger = logging.getLogger(__name__)


class LinearSolver:
    """Linear programming solver using PuLP."""

    def __init__(self, timeout_seconds: int = 30):
        """Initialize solver."""
        self.timeout_seconds = timeout_seconds

    def solve(
        self,
        problem: OptimizationProblem,
        optimization_run_id: UUID,
    ) -> OptimizationSolution:
        """Solve the optimization problem."""
        try:
            # Create LP problem
            lp_problem = LpProblem(f"BehaviorOptimization_{optimization_run_id}", LpMaximize)

            # Decision variables
            behaviors = problem.behaviors
            time_periods = problem.time_periods

            # Binary scheduling variables: x[b,t] indicates if behavior b is scheduled in period t
            x = {}
            for b_idx, behavior in enumerate(behaviors):
                for t in range(time_periods):
                    x[(b_idx, t)] = LpVariable(f"x_{b_idx}_{t}", cat="Binary")

            # Continuous duration variables: d[b,t] is duration of behavior b in period t
            d = {}
            for b_idx, behavior in enumerate(behaviors):
                for t in range(time_periods):
                    d[(b_idx, t)] = LpVariable(
                        f"d_{b_idx}_{t}",
                        lowBound=0,
                        cat="Continuous",
                    )

            # Objective: weighted sum of objective contributions
            objective = 0
            for obj_type, weight in problem.objectives.items():
                obj_value = 0
                for b_idx, behavior in enumerate(behaviors):
                    impact = behavior.impacts.get(obj_type, 0.0)
                    for t in range(time_periods):
                        obj_value += impact * d[(b_idx, t)]

                objective += weight * obj_value

            lp_problem += objective

            # Constraints
            # 1. Duration bounds for scheduled behaviors
            for b_idx, behavior in enumerate(behaviors):
                for t in range(time_periods):
                    # If scheduled, duration must be between min and max
                    lp_problem += (
                        d[(b_idx, t)] >= behavior.min_duration * x[(b_idx, t)],
                        f"min_duration_{b_idx}_{t}",
                    )
                    lp_problem += (
                        d[(b_idx, t)] <= behavior.max_duration * x[(b_idx, t)],
                        f"max_duration_{b_idx}_{t}",
                    )

            # 2. Time budget constraints (from constraints)
            for constraint in problem.active_constraints:
                if constraint.type == "time_budget":
                    params = constraint.parameters
                    max_daily_minutes = params.get("max_daily_minutes", 480)
                    
                    for t in range(time_periods):
                        period_duration = lpSum(
                            d[(b_idx, t)] for b_idx in range(len(behaviors))
                        )
                        lp_problem += (
                            period_duration <= max_daily_minutes,
                            f"time_budget_{t}",
                        )

                elif constraint.type == "frequency":
                    params = constraint.parameters
                    behavior_id = params.get("behavior_id")
                    min_freq = params.get("min_frequency", 0)
                    max_freq = params.get("max_frequency", time_periods)
                    
                    try:
                        b_idx = next(
                            i
                            for i, b in enumerate(behaviors)
                            if str(b.id) == str(behavior_id)
                        )
                        frequency = lpSum(x[(b_idx, t)] for t in range(time_periods))
                        lp_problem += frequency >= min_freq, f"min_freq_{behavior_id}"
                        lp_problem += frequency <= max_freq, f"max_freq_{behavior_id}"
                    except StopIteration:
                        logger.warning(f"Behavior {behavior_id} not found for frequency constraint")

            # Solve
            solver = PULP_CBC_CMD(timeLimit=self.timeout_seconds, msg=0)
            lp_problem.solve(solver)

            # Check status
            status = LpStatus[lp_problem.status]
            if status == "Infeasible":
                raise InfeasibleProblemError("Problem is infeasible with current constraints")
            elif status == "Unbounded":
                raise UnboundedProblemError("Problem is unbounded")
            elif status not in ["Optimal", "Not Solved"]:
                if status == "Undefined":
                    raise SolverError(f"Solver returned undefined status: {status}")

            # Extract solution
            schedule_items = []
            for b_idx, behavior in enumerate(behaviors):
                for t in range(time_periods):
                    if x[(b_idx, t)].varValue == 1:
                        duration = int(d[(b_idx, t)].varValue) if d[(b_idx, t)].varValue else 0
                        if duration > 0:
                            schedule_items.append(
                                ScheduleItem(
                                    behavior_id=behavior.id,
                                    behavior_name=behavior.name,
                                    time_period=t,
                                    scheduled_duration=duration,
                                    is_scheduled=True,
                                )
                            )

            # Calculate objective contributions
            objective_contributions = {}
            total_value = lp_problem.objective.value() if status == "Optimal" else 0

            for obj_type, weight in problem.objectives.items():
                contribution = 0
                for b_idx, behavior in enumerate(behaviors):
                    impact = behavior.impacts.get(obj_type, 0.0)
                    for t in range(time_periods):
                        if d[(b_idx, t)].varValue:
                            contribution += impact * d[(b_idx, t)].varValue

                objective_contributions[obj_type] = ObjectiveContribution(
                    objective_type=obj_type,
                    contribution=contribution * weight if weight else 0,
                    weight=weight,
                )

            return OptimizationSolution(
                optimization_run_id=optimization_run_id,
                status="optimal" if status == "Optimal" else "feasible",
                solver="linear",
                total_objective_value=total_value,
                schedule_items=schedule_items,
                objective_contributions=objective_contributions,
                diagnostics={"solver_status": status},
            )

        except (InfeasibleProblemError, UnboundedProblemError):
            raise
        except TimeoutError:
            raise SolverTimeoutError(f"Solver timeout after {self.timeout_seconds} seconds")
        except Exception as e:
            logger.error(f"Solver error: {str(e)}")
            raise SolverError(f"Solver encountered an error: {str(e)}")
