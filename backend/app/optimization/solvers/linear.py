"""Linear programming solver for behavior optimization."""
import logging
from typing import Dict, List, Optional, Any
from uuid import UUID

from pulp import (
    LpMaximize,
    LpProblem,
    LpVariable,
    lpSum,
    LpConstraint,
    PULP_CBC_CMD,
    LpStatus,
)

from app.core.constants import MINUTES_PER_PERIOD, PERIODS_PER_DAY
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

# Map TimeSlot enum values to a set of allowable period indices (0 … 95).
_TIME_SLOT_PERIODS: dict[str, set[int]] = {
    "early_morning": set(range(0, 16)),
    "morning":       set(range(16, 32)),
    "midday":        set(range(32, 48)),
    "afternoon":     set(range(48, 64)),
    "evening":       set(range(64, 80)),
    "night":         set(range(80, 96)),
    "flexible":      set(range(96)),   # entire day
}


class LinearSolver:
    """Linear programming solver using PuLP.

    Formulates a **true combinatorial 24-hour MILP** with a 96-period
    (15-minute-block) binary decision matrix ``x[b, t]``.

    Constraints
    -----------
    - **Time-slot exclusivity** — at most one behavior per period.
    - **Preference windows** — ``x[b, t] = 0`` for blocks outside the
      behavior's ``preferred_time_slots``.
    - **Duration bounds** — total scheduled minutes per behavior is bounded
      by ``[min_duration, max_duration]``.
    - **Daily time budget** — total scheduled minutes across *all* behaviors
      may not exceed ``max_daily_minutes``.
    - **Frequency** — total assigned periods per behavior is bounded by
      ``[min_frequency, max_frequency]``.
    """

    def __init__(self, timeout_seconds: int = 30):
        self.timeout_seconds = timeout_seconds

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _periods_for_slots(slot_names: list[str]) -> set[int]:
        """Return the union of period indices allowed by *slot_names*."""
        if not slot_names:
            return set(range(PERIODS_PER_DAY))
        allowed = set()
        for name in slot_names:
            allowed.update(_TIME_SLOT_PERIODS.get(name, set(range(PERIODS_PER_DAY))))
        return allowed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def solve(
        self,
        problem: OptimizationProblem,
        optimization_run_id: UUID,
    ) -> OptimizationSolution:
        """Solve the optimization problem."""
        try:
            lp = LpProblem(f"BehaviorOptimization_{optimization_run_id}", LpMaximize)

            behaviors = problem.behaviors
            T = problem.time_periods  # should be 96 for a full-day schedule
            B = len(behaviors)

            # ---- decision variables -------------------------------------------
            # x[b, t] = 1  ⇔ behavior b occupies 15-minute block t
            x: dict[tuple[int, int], LpVariable] = {}
            for b_idx in range(B):
                for t in range(T):
                    x[(b_idx, t)] = LpVariable(f"x_{b_idx}_{t}", cat="Binary")

            # ---- objective: weighted sum of impacts × scheduled minutes -------
            objective = 0
            for obj_type, weight in problem.objectives.items():
                obj_value = 0
                for b_idx, behavior in enumerate(behaviors):
                    impact = behavior.impacts.get(obj_type, 0.0)
                    obj_value += impact * lpSum(
                        x[(b_idx, t)] for t in range(T)
                    )
                objective += weight * obj_value * MINUTES_PER_PERIOD

            lp += objective, "total_weighted_objective"

            # ---- constraint (1): time-slot exclusivity ------------------------
            # At most one behavior per 15-minute block.
            for t in range(T):
                lp += (
                    lpSum(x[(b_idx, t)] for b_idx in range(B)) <= 1,
                    f"exclusivity_t{t}",
                )

            # ---- constraint (2): preference windows ---------------------------
            # x[b, t] = 0 for any block outside the behavior's preferred slots.
            for b_idx, behavior in enumerate(behaviors):
                allowed = self._periods_for_slots(behavior.preferred_time_slots)
                for t in range(T):
                    if t not in allowed:
                        lp += x[(b_idx, t)] == 0, f"pref_{b_idx}_t{t}"

            # ---- constraint (3): duration bounds per behavior -----------------
            # Sum of assigned periods * MINUTES_PER_PERIOD in [min, max].
            for b_idx, behavior in enumerate(behaviors):
                total_periods = lpSum(x[(b_idx, t)] for t in range(T))
                lp += (
                    total_periods * MINUTES_PER_PERIOD >= behavior.min_duration,
                    f"min_dur_{b_idx}",
                )
                lp += (
                    total_periods * MINUTES_PER_PERIOD <= behavior.max_duration,
                    f"max_dur_{b_idx}",
                )

            # ---- constraint (4): daily time / energy budget -------------------
            for constraint in problem.active_constraints:
                params = constraint.parameters

                if constraint.type == "time_budget":
                    max_daily_minutes = params.get("max_daily_minutes", 480)
                    total_duration = lpSum(
                        x[(b_idx, t)] * MINUTES_PER_PERIOD
                        for b_idx in range(B)
                        for t in range(T)
                    )
                    lp += total_duration <= max_daily_minutes, "time_budget"

                elif constraint.type == "frequency":
                    behavior_id = params.get("behavior_id")
                    min_freq = params.get("min_frequency", 0)
                    max_freq = params.get("max_frequency", T)

                    try:
                        b_idx = next(
                            i
                            for i, b in enumerate(behaviors)
                            if str(b.id) == str(behavior_id)
                        )
                        freq = lpSum(x[(b_idx, t)] for t in range(T))
                        lp += freq >= min_freq, f"min_freq_{behavior_id}"
                        lp += freq <= max_freq, f"max_freq_{behavior_id}"
                    except StopIteration:
                        logger.warning(
                            "Behavior %s not found for frequency constraint",
                            behavior_id,
                        )

            # ---- solve --------------------------------------------------------
            solver = PULP_CBC_CMD(timeLimit=self.timeout_seconds, msg=0)
            lp.solve(solver)

            status = LpStatus[lp.status]
            if status == "Infeasible":
                raise InfeasibleProblemError(
                    "Problem is infeasible with current constraints"
                )
            if status == "Unbounded":
                raise UnboundedProblemError("Problem is unbounded")
            if status not in ("Optimal", "Not Solved"):
                if status == "Undefined":
                    raise SolverError(f"Solver returned undefined status: {status}")

            # ---- extract schedule items ---------------------------------------
            schedule_items: list[ScheduleItem] = []
            for b_idx, behavior in enumerate(behaviors):
                blocks: list[int] = []
                for t in range(T):
                    if x[(b_idx, t)].varValue and x[(b_idx, t)].varValue > 0.5:
                        blocks.append(t)

                if not blocks:
                    continue

                # Merge consecutive blocks into sessions and emit one
                # ScheduleItem per contiguous run.  The solver does not
                # explicitly link consecutive blocks together, so we
                # post-process here.
                sessions: list[tuple[int, int]] = []
                start = blocks[0]
                prev = blocks[0]
                for p in blocks[1:]:
                    if p != prev + 1:
                        sessions.append((start, prev))
                        start = p
                    prev = p
                sessions.append((start, prev))

                for s_start, s_end in sessions:
                    n_blocks = s_end - s_start + 1
                    duration = n_blocks * MINUTES_PER_PERIOD
                    schedule_items.append(
                        ScheduleItem(
                            behavior_id=behavior.id,
                            behavior_name=behavior.name,
                            time_period=s_start,
                            scheduled_duration=duration,
                            is_scheduled=True,
                        )
                    )

            # ---- objective contributions --------------------------------------
            total_value = lp.objective.value() or 0.0 if status == "Optimal" else 0.0
            objective_contributions: dict[str, ObjectiveContribution] = {}

            for obj_type, weight in problem.objectives.items():
                contribution = 0.0
                for b_idx, behavior in enumerate(behaviors):
                    impact = behavior.impacts.get(obj_type, 0.0)
                    has_blocks = any(
                        x[(b_idx, t)].varValue and x[(b_idx, t)].varValue > 0.5
                        for t in range(T)
                    )
                    if has_blocks:
                        contribution += impact
                contribution *= weight
                objective_contributions[obj_type] = ObjectiveContribution(
                    objective_type=obj_type,
                    contribution=round(contribution, 4),
                    weight=weight,
                )

            scaled_total = total_value / MINUTES_PER_PERIOD

            return OptimizationSolution(
                optimization_run_id=optimization_run_id,
                status="optimal" if status == "Optimal" else "feasible",
                solver="linear",
                total_objective_value=round(scaled_total, 4),
                schedule_items=schedule_items,
                objective_contributions=objective_contributions,
                diagnostics={"solver_status": status},
            )

        except (InfeasibleProblemError, UnboundedProblemError):
            raise
        except TimeoutError:
            raise SolverTimeoutError(
                f"Solver timeout after {self.timeout_seconds} seconds"
            )
        except Exception as e:
            logger.exception("Solver error")
            raise SolverError(f"Solver encountered an error: {e}") from e

    # ------------------------------------------------------------------
    # Partial-day re-optimization
    # ------------------------------------------------------------------

    def solve_partial_day(
        self,
        problem: OptimizationProblem,
        optimization_run_id: UUID,
        frozen_periods: dict[int, dict[int, int]],
    ) -> OptimizationSolution:
        """Re-solve the remaining periods of a single day.

        ``frozen_periods`` maps ``{behavior_idx: {period: 1_or_0}}`` for
        all periods that have already elapsed (past periods).  These
        variables are fixed to their current value so the solver only
        rearranges the future.

        Parameters
        ----------
        problem:
            The full-day problem specification (used for objective weights,
            constraints, and behavior metadata).
        optimization_run_id:
            ID of the *new* OptimizationRun being created for this re-solve.
        frozen_periods:
            ``{b_idx: {t: 0_or_1, ...}, ...}`` — variables to pin.

        Returns
        -------
        OptimizationSolution
            Solution covering the *entire* day (frozen + re-solved).
        """
        try:
            lp = LpProblem(f"PartialReopt_{optimization_run_id}", LpMaximize)

            behaviors = problem.behaviors
            T = problem.time_periods
            B = len(behaviors)

            # Determine the earliest unfrozen period
            all_frozen_t = set()
            for period_map in frozen_periods.values():
                all_frozen_t.update(period_map.keys())
            earliest_free = max(all_frozen_t) + 1 if all_frozen_t else 0

            # ---- decision variables -----------------------------------------
            x: dict[tuple[int, int], LpVariable] = {}
            for b_idx in range(B):
                for t in range(T):
                    if t < earliest_free:
                        # Frozen — constant
                        val = frozen_periods.get(b_idx, {}).get(t, 0)
                        x[(b_idx, t)] = LpVariable(
                            f"x_{b_idx}_{t}", lowBound=val, upBound=val, cat="Binary"
                        )
                    else:
                        x[(b_idx, t)] = LpVariable(f"x_{b_idx}_{t}", cat="Binary")

            # ---- objective (identical to full solve) -----------------------
            objective = 0
            for obj_type, weight in problem.objectives.items():
                obj_value = 0
                for b_idx, behavior in enumerate(behaviors):
                    impact = behavior.impacts.get(obj_type, 0.0)
                    obj_value += impact * lpSum(x[(b_idx, t)] for t in range(T))
                objective += weight * obj_value * MINUTES_PER_PERIOD
            lp += objective, "total_weighted_objective"

            # ---- constraints (same as full solve) ---------------------------
            # Exclusivity
            for t in range(T):
                lp += (
                    lpSum(x[(b_idx, t)] for b_idx in range(B)) <= 1,
                    f"exclusivity_t{t}",
                )

            # Preference windows
            for b_idx, behavior in enumerate(behaviors):
                allowed = self._periods_for_slots(behavior.preferred_time_slots)
                for t in range(T):
                    if t not in allowed:
                        lp += x[(b_idx, t)] == 0, f"pref_{b_idx}_t{t}"

            # Duration bounds — only for the *remaining* duration.
            # Each behavior needs at least min_duration minutes total;
            # the frozen part already contributes some minutes.
            for b_idx, behavior in enumerate(behaviors):
                frozen_minutes = sum(
                    frozen_periods.get(b_idx, {}).get(t, 0) * MINUTES_PER_PERIOD
                    for t in range(earliest_free)
                )
                remaining_min = max(0, behavior.min_duration - frozen_minutes)
                remaining_max = max(0, behavior.max_duration - frozen_minutes)
                if remaining_min > 0:
                    lp += (
                        lpSum(x[(b_idx, t)] for t in range(earliest_free, T))
                        * MINUTES_PER_PERIOD
                        >= remaining_min,
                        f"min_dur_{b_idx}",
                    )
                if remaining_max > 0:
                    lp += (
                        lpSum(x[(b_idx, t)] for t in range(earliest_free, T))
                        * MINUTES_PER_PERIOD
                        <= remaining_max,
                        f"max_dur_{b_idx}",
                    )

            # Daily time / energy budget
            for constraint in problem.active_constraints:
                params = constraint.parameters
                if constraint.type == "time_budget":
                    max_daily_minutes = params.get("max_daily_minutes", 480)
                    frozen_total = sum(
                        frozen_periods.get(b, {}).get(t, 0) * MINUTES_PER_PERIOD
                        for b in range(B)
                        for t in range(earliest_free)
                    )
                    remaining_budget = max(0, max_daily_minutes - frozen_total)
                    if remaining_budget > 0:
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
                            i for i, b in enumerate(behaviors)
                            if str(b.id) == str(behavior_id)
                        )
                        frozen_freq = sum(
                            frozen_periods.get(b_idx, {}).get(t, 0)
                            for t in range(earliest_free)
                        )
                        remaining_min_f = max(0, min_freq - frozen_freq)
                        remaining_max_f = max(0, max_freq - frozen_freq)
                        freq = lpSum(x[(b_idx, t)] for t in range(earliest_free, T))
                        if remaining_min_f > 0:
                            lp += freq >= remaining_min_f, f"min_freq_{behavior_id}"
                        if remaining_max_f > 0:
                            lp += freq <= remaining_max_f, f"max_freq_{behavior_id}"
                    except StopIteration:
                        pass

            # ---- solve ------------------------------------------------------
            solver = PULP_CBC_CMD(timeLimit=self.timeout_seconds, msg=0)
            lp.solve(solver)

            status = LpStatus[lp.status]
            if status == "Infeasible":
                raise InfeasibleProblemError(
                    "Partial re-opt is infeasible with current frozen periods"
                )
            if status == "Unbounded":
                raise UnboundedProblemError("Partial re-opt is unbounded")
            if status not in ("Optimal", "Not Solved"):
                if status == "Undefined":
                    raise SolverError(f"Solver returned undefined status: {status}")

            # ---- extract schedule items (same as full solve) ----------------
            schedule_items: list[ScheduleItem] = []
            for b_idx, behavior in enumerate(behaviors):
                blocks: list[int] = []
                for t in range(T):
                    if x[(b_idx, t)].varValue and x[(b_idx, t)].varValue > 0.5:
                        blocks.append(t)

                if not blocks:
                    continue

                sessions: list[tuple[int, int]] = []
                start = blocks[0]
                prev = blocks[0]
                for p in blocks[1:]:
                    if p != prev + 1:
                        sessions.append((start, prev))
                        start = p
                    prev = p
                sessions.append((start, prev))

                for s_start, s_end in sessions:
                    n_blocks = s_end - s_start + 1
                    duration = n_blocks * MINUTES_PER_PERIOD
                    schedule_items.append(
                        ScheduleItem(
                            behavior_id=behavior.id,
                            behavior_name=behavior.name,
                            time_period=s_start,
                            scheduled_duration=duration,
                            is_scheduled=True,
                        )
                    )

            # ---- objective contributions ------------------------------------
            total_value = lp.objective.value() or 0.0 if status == "Optimal" else 0.0
            objective_contributions: dict[str, ObjectiveContribution] = {}
            for obj_type, weight in problem.objectives.items():
                contribution = 0.0
                for b_idx, behavior in enumerate(behaviors):
                    impact = behavior.impacts.get(obj_type, 0.0)
                    for t in range(T):
                        if x[(b_idx, t)].varValue and x[(b_idx, t)].varValue > 0.5:
                            contribution += impact * MINUTES_PER_PERIOD
                contribution *= weight
                objective_contributions[obj_type] = ObjectiveContribution(
                    objective_type=obj_type,
                    contribution=round(contribution, 4),
                    weight=weight,
                )

            return OptimizationSolution(
                optimization_run_id=optimization_run_id,
                status="optimal" if status == "Optimal" else "feasible",
                solver="linear_partial",
                total_objective_value=round(total_value, 4),
                schedule_items=schedule_items,
                objective_contributions=objective_contributions,
                diagnostics={
                    "solver_status": status,
                    "frozen_periods_count": len(all_frozen_t),
                    "earliest_free_period": earliest_free,
                },
            )

        except (InfeasibleProblemError, UnboundedProblemError):
            raise
        except TimeoutError:
            raise SolverTimeoutError(
                f"Solver timeout after {self.timeout_seconds} seconds"
            )
        except Exception as e:
            logger.exception("Partial re-opt solver error")
            raise SolverError(f"Partial re-opt encountered an error: {e}") from e
