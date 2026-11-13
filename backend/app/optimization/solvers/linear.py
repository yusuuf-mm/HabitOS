"""Linear programming solver for behavior optimization.

Formulates a 24-hour MILP with a 96-period (15-minute-block) binary decision
matrix ``x[b, t]``. The full-day solve and the partial-day re-solve share one
formulation and one objective definition (``app.optimization.objective``), so the
two paths cannot report different values for the same schedule.

Constraints
-----------
- Time-slot exclusivity: at most one behaviour per period.
- Preference windows: ``x[b, t] = 0`` outside the behaviour's windows.
- Duration bounds: scheduled minutes per behaviour within ``[min, max]``.
- Daily time budget, and per-behaviour frequency bounds when configured.

Result contract
---------------
``Optimal`` is returned as a plan. A non-optimal status is never turned into a
plan: by default it raises, and with ``accept_nonoptimal=True`` the result is only
returned after :func:`app.optimization.status.validate_schedule` passes.
"""

import logging
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from pulp import (
    LpMaximize,
    LpProblem,
    LpVariable,
    lpSum,
    PULP_CBC_CMD,
    LpStatus,
)

from app.core.constants import MINUTES_PER_PERIOD, periods_for_time_slots
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
)
from app.optimization.objective import (
    objective_contributions as build_contributions,
    total_objective_value as compute_total,
)
from app.optimization.status import INTEGRAL_TOLERANCE, SolveStatus, validate_schedule

logger = logging.getLogger(__name__)


class LinearSolver:
    """MILP solver for the daily plan, using PuLP + CBC."""

    def __init__(self, timeout_seconds: int = 30, accept_nonoptimal: bool = False):
        self.timeout_seconds = timeout_seconds
        self.accept_nonoptimal = accept_nonoptimal

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _periods_for_slots(slot_names: list[str]) -> set[int]:
        """Union of period indices allowed by *slot_names* (canonical windows)."""
        return periods_for_time_slots(slot_names)

    def _run_solver(self, lp: LpProblem) -> str:
        """Solve *lp* and return the PuLP status name. Patchable in tests."""
        lp.solve(PULP_CBC_CMD(timeLimit=self.timeout_seconds, msg=0))
        return LpStatus[lp.status]

    def _add_windows(
        self,
        lp: LpProblem,
        x: Dict[Tuple[int, int], LpVariable],
        problem: OptimizationProblem,
        periods: int,
    ) -> None:
        for b_idx, behavior in enumerate(problem.behaviors):
            allowed = self._periods_for_slots(
                [s.value if hasattr(s, "value") else str(s) for s in behavior.preferred_time_slots]
            )
            for t in range(periods):
                if t not in allowed:
                    lp += x[(b_idx, t)] == 0, f"pref_{b_idx}_t{t}"

    def _extract_items(
        self,
        x: Dict[Tuple[int, int], LpVariable],
        problem: OptimizationProblem,
        start_period: int = 0,
    ) -> List[ScheduleItem]:
        """Turn the assignment matrix into contiguous sessions."""
        items: List[ScheduleItem] = []
        for b_idx, behavior in enumerate(problem.behaviors):
            blocks: List[int] = [
                t
                for t in range(problem.time_periods)
                if x[(b_idx, t)].varValue and round(x[(b_idx, t)].varValue) == 1
            ]
            if not blocks:
                continue

            sessions: List[Tuple[int, int]] = []
            start = prev = blocks[0]
            for period in blocks[1:]:
                if period != prev + 1:
                    sessions.append((start, prev))
                    start = period
                prev = period
            sessions.append((start, prev))

            for s_start, s_end in sessions:
                duration = (s_end - s_start + 1) * MINUTES_PER_PERIOD
                items.append(
                    ScheduleItem(
                        behavior_id=behavior.id,
                        behavior_name=behavior.name,
                        time_period=s_start + start_period,
                        scheduled_duration=duration,
                        is_scheduled=True,
                    )
                )
        return items

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def solve(
        self,
        problem: OptimizationProblem,
        optimization_run_id: UUID,
    ) -> OptimizationSolution:
        """Solve the full day."""
        return self._solve(problem, optimization_run_id, frozen_periods=None)

    def solve_partial_day(
        self,
        problem: OptimizationProblem,
        optimization_run_id: UUID,
        frozen_periods: Dict[int, Dict[int, int]],
    ) -> OptimizationSolution:
        """Re-solve the day with the elapsed part pinned.

        ``frozen_periods`` maps ``{behavior_idx: {period: 0_or_1}}``; every period
        up to the latest frozen one is fixed to its recorded value.
        """
        return self._solve(problem, optimization_run_id, frozen_periods=frozen_periods)

    # ------------------------------------------------------------------
    # Shared implementation
    # ------------------------------------------------------------------

    def _solve(
        self,
        problem: OptimizationProblem,
        optimization_run_id: UUID,
        frozen_periods: Optional[Dict[int, Dict[int, int]]],
    ) -> OptimizationSolution:
        partial = frozen_periods is not None
        frozen_periods = frozen_periods or {}

        all_frozen_t = {t for periods in frozen_periods.values() for t in periods}
        earliest_free = max(all_frozen_t) + 1 if all_frozen_t else 0

        try:
            lp = LpProblem(f"BehaviorOptimization_{optimization_run_id}", LpMaximize)
            behaviors = problem.behaviors
            T = problem.time_periods
            B = len(behaviors)

            x: Dict[Tuple[int, int], LpVariable] = {}
            for b_idx in range(B):
                for t in range(T):
                    x[(b_idx, t)] = LpVariable(f"x_{b_idx}_{t}", cat="Binary")
                    # PuLP resets lowBound/upBound for cat="Binary", so a frozen
                    # value must be pinned with a constraint, not with bounds.
                    if partial and t < earliest_free:
                        val = frozen_periods.get(b_idx, {}).get(t, 0)
                        lp += x[(b_idx, t)] == val, f"frozen_{b_idx}_t{t}"

            # ---- objective: weighted impacts x scheduled minutes -----------
            # The value reported to callers is recomputed from the schedule in
            # ``app.optimization.objective``; this expression only steers CBC.
            expression = 0
            for obj_type, weight in problem.objectives.items():
                obj_value = 0
                for b_idx, behavior in enumerate(behaviors):
                    impact = behavior.impacts.get(obj_type, 0.0)
                    obj_value += impact * lpSum(x[(b_idx, t)] for t in range(T))
                expression += weight * obj_value * MINUTES_PER_PERIOD
            lp += expression, "total_weighted_objective"

            # ---- exclusivity ------------------------------------------------
            for t in range(T):
                lp += (
                    lpSum(x[(b_idx, t)] for b_idx in range(B)) <= 1,
                    f"exclusivity_t{t}",
                )

            # ---- windows ----------------------------------------------------
            self._add_windows(lp, x, problem, T)

            # ---- duration bounds (remaining minutes when frozen) ------------
            for b_idx, behavior in enumerate(behaviors):
                frozen_minutes = sum(
                    frozen_periods.get(b_idx, {}).get(t, 0) * MINUTES_PER_PERIOD
                    for t in range(earliest_free)
                )
                remaining_min = max(0, behavior.min_duration - frozen_minutes)
                remaining_max = max(0, behavior.max_duration - frozen_minutes)
                free_periods = lpSum(x[(b_idx, t)] for t in range(earliest_free, T))

                if remaining_min > 0:
                    lp += free_periods * MINUTES_PER_PERIOD >= remaining_min, f"min_dur_{b_idx}"
                elif not partial:
                    lp += free_periods * MINUTES_PER_PERIOD >= behavior.min_duration, f"min_dur_{b_idx}"

                if remaining_max > 0:
                    lp += free_periods * MINUTES_PER_PERIOD <= remaining_max, f"max_dur_{b_idx}"

            # ---- daily budget and frequency ---------------------------------
            for constraint in problem.active_constraints:
                params = constraint.parameters

                if constraint.type == "time_budget":
                    max_daily_minutes = params.get("max_daily_minutes", 480)
                    frozen_total = sum(
                        frozen_periods.get(b, {}).get(t, 0) * MINUTES_PER_PERIOD
                        for b in range(B)
                        for t in range(earliest_free)
                    )
                    remaining_budget = max_daily_minutes - frozen_total
                    lp += (
                        lpSum(
                            x[(b_idx, t)] * MINUTES_PER_PERIOD
                            for b_idx in range(B)
                            for t in range(earliest_free, T)
                        )
                        <= remaining_budget,
                        "time_budget",
                    )

                elif constraint.type == "frequency":
                    behavior_id = params.get("behavior_id")
                    min_freq = params.get("min_frequency", 0)
                    max_freq = params.get("max_frequency", T)
                    try:
                        b_idx = next(
                            i for i, b in enumerate(behaviors) if str(b.id) == str(behavior_id)
                        )
                    except StopIteration:
                        logger.warning(
                            "Behavior %s not found for frequency constraint", behavior_id
                        )
                        continue

                    frozen_freq = sum(
                        frozen_periods.get(b_idx, {}).get(t, 0) for t in range(earliest_free)
                    )
                    freq = lpSum(x[(b_idx, t)] for t in range(earliest_free, T))
                    remaining_min_f = max(0, min_freq - frozen_freq)
                    remaining_max_f = max(0, max_freq - frozen_freq)
                    if remaining_min_f > 0:
                        lp += freq >= remaining_min_f, f"min_freq_{behavior_id}"
                    if remaining_max_f > 0:
                        lp += freq <= remaining_max_f, f"max_freq_{behavior_id}"

            # ---- solve ------------------------------------------------------
            status = self._run_solver(lp)

            if status == "Infeasible":
                raise InfeasibleProblemError(
                    "No plan satisfies the current constraints"
                    + (" with the elapsed sessions frozen" if partial else "")
                )
            if status == "Unbounded":
                raise UnboundedProblemError("The problem is unbounded")
            if status not in ("Optimal", "Not Solved"):
                raise SolverError(f"Solver returned status {status}")

            if status != "Optimal":
                # A time-limited CBC run still populates variables with
                # relaxation values. Never present those as a plan.
                if not self.accept_nonoptimal:
                    raise SolverTimeoutError(
                        f"Solver did not reach optimality within {self.timeout_seconds} seconds"
                    )

            # Integrality of the returned values, checked independently of the
            # status the solver claims. A relaxation is never a plan.
            fractional = [
                f"x[{b_idx},{period}]={value.varValue}"
                for (b_idx, period), value in x.items()
                if value.varValue is not None
                and abs(value.varValue - round(value.varValue)) > INTEGRAL_TOLERANCE
            ]
            if fractional:
                raise SolverError(
                    "Solver result is not integral ("
                    + ", ".join(fractional[:5])
                    + "); refusing to build a plan from a relaxation"
                )

            items = self._extract_items(x, problem)

            violations = validate_schedule(problem, items)
            if violations:
                raise SolverError(
                    "Solver produced a schedule that fails validation: "
                    + "; ".join(violations[:5])
                )

            behaviors_by_id = {b.id: b for b in behaviors}
            total_value = compute_total(problem.objectives, behaviors_by_id, items)
            contributions = build_contributions(problem.objectives, behaviors_by_id, items)

            diagnostics = {
                "solver_status": status,
                "solve_status": (
                    SolveStatus.OPTIMAL.value if status == "Optimal" else SolveStatus.FEASIBLE.value
                ),
            }
            if partial:
                diagnostics["frozen_periods_count"] = len(all_frozen_t)
                diagnostics["earliest_free_period"] = earliest_free

            return OptimizationSolution(
                optimization_run_id=optimization_run_id,
                status=SolveStatus.OPTIMAL.value if status == "Optimal" else SolveStatus.FEASIBLE.value,
                solver="linear_partial" if partial else "linear",
                total_objective_value=total_value,
                schedule_items=items,
                objective_contributions=contributions,
                diagnostics=diagnostics,
            )

        except (InfeasibleProblemError, UnboundedProblemError, SolverTimeoutError, SolverError):
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Solver error")
            raise SolverError("Solver encountered an unexpected error") from exc
