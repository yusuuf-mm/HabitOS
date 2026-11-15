"""Candidate-placement solver: the production formulation (docs/FORMULATION.md).

One binary per *candidate session* instead of one per (behaviour, period). A
selected candidate is contiguous by construction, its length is one of at most
eight steps inside the behaviour's bounds, and every behaviour is either placed
or explicitly declined — silence is not an outcome.

What is unchanged from the block model it replaces: `OptimizationProblem` in,
`OptimizationSolution` out, `validate_schedule` before anything is returned, the
shared `objective.py` value, and the worker pool that runs it. What changed: the
plan can report *why* a behaviour is missing, and a candidate can never be split
into fragments the user did not ask for.

Size limits
-----------
- 25 active behaviours per plan; above that the solve is refused with a message
  instead of being silently truncated.
- At most 8 candidate lengths per behaviour, always including min and max.
- Starts align to 30 minutes when the length is a multiple of 30 minutes.
"""

from __future__ import annotations

import math
import time
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple
from uuid import UUID

import pulp

from app.core.constants import MINUTES_PER_PERIOD, PERIODS_PER_DAY, periods_for_time_slots
from app.core.exceptions import (
    InfeasibleProblemError,
    SolverError,
    SolverTimeoutError,
)
from app.optimization.models import (
    BehaviorScheduleInput,
    OptimizationProblem,
    OptimizationSolution,
    ScheduleItem,
)
from app.optimization.objective import (
    objective_contributions as build_contributions,
    total_objective_value as compute_total,
)
from app.optimization.status import SolveStatus, validate_schedule

MAX_BEHAVIORS = 25
MAX_DURATION_OPTIONS = 8
ALIGN_PERIODS = 2  # 30 minutes

# Declines are last resort: declining costs at least the value of the shortest
# session the behaviour would have earned, plus a tie-break so that a
# zero-value behaviour is still placed when there is room for it.
DECLINE_TIE_BREAK = 1e-3

Window = Tuple[int, int]  # half-open period range


def duration_options(min_duration: int, max_duration: int) -> List[int]:
    """Candidate lengths in periods: at most 8, always including max."""
    lo = max(1, math.ceil(min_duration / MINUTES_PER_PERIOD))
    hi = max(lo, math.floor(max_duration / MINUTES_PER_PERIOD))
    count = hi - lo + 1
    if count <= MAX_DURATION_OPTIONS:
        return list(range(lo, hi + 1))
    step = math.ceil((count - 1) / (MAX_DURATION_OPTIONS - 1))
    options = list(range(lo, hi + 1, step))
    if options[-1] != hi:
        options[-1] = hi
    return options


def contiguous_ranges(periods: Iterable[int], limit: int = PERIODS_PER_DAY) -> List[Window]:
    """Turn a set of allowed periods into half-open contiguous ranges."""
    ordered = sorted(p for p in periods if 0 <= p < limit)
    ranges: List[Window] = []
    if not ordered:
        return ranges
    start = prev = ordered[0]
    for period in ordered[1:]:
        if period == prev + 1:
            prev = period
            continue
        ranges.append((start, prev + 1))
        start = prev = period
    ranges.append((start, prev + 1))
    return ranges


def generate_candidates(
    windows: Sequence[Window],
    min_duration: int,
    max_duration: int,
    earliest: int,
    periods: int = PERIODS_PER_DAY,
) -> List[Tuple[int, int]]:
    """Every contiguous run inside one window whose length is one of the options."""
    out: List[Tuple[int, int]] = []
    if max_duration <= 0 or min_duration > max_duration:
        return out
    for length in duration_options(min_duration, max_duration):
        step = ALIGN_PERIODS if length % ALIGN_PERIODS == 0 else 1
        for window_start, window_end in windows:
            start_limit = max(window_start, earliest)
            if start_limit % step != 0:
                start_limit += step - (start_limit % step)
            for start in range(start_limit, min(window_end, periods) - length + 1, step):
                out.append((start, length))
    return out


def _score(behavior: BehaviorScheduleInput, weights: Dict[str, float]) -> float:
    return sum(
        weight * behavior.impacts.get(objective_type, 0.0)
        for objective_type, weight in weights.items()
    )


def _frozen_runs(periods_with_sessions: Iterable[int]) -> List[Tuple[int, int]]:
    """Contiguous runs of already-elapsed periods, as (start, length)."""
    ordered = sorted(set(periods_with_sessions))
    runs: List[Tuple[int, int]] = []
    if not ordered:
        return runs
    start = prev = ordered[0]
    for period in ordered[1:]:
        if period == prev + 1:
            prev = period
            continue
        runs.append((start, prev - start + 1))
        start = prev = period
    runs.append((start, prev - start + 1))
    return runs


class CandidateSolver:
    """Candidate-placement MILP. Same public API as the block solver."""

    def __init__(self, timeout_seconds: int = 30, accept_nonoptimal: bool = False):
        self.timeout_seconds = timeout_seconds
        self.accept_nonoptimal = accept_nonoptimal

    # -- public API ------------------------------------------------------

    def solve(self, problem: OptimizationProblem, optimization_run_id: UUID) -> OptimizationSolution:
        """Solve the whole day."""
        return self._solve(problem, optimization_run_id, frozen_periods=None, forced_ids=())

    def solve_partial_day(
        self,
        problem: OptimizationProblem,
        optimization_run_id: UUID,
        frozen_periods: Dict[int, Dict[int, int]],
    ) -> OptimizationSolution:
        """Re-solve the future with every elapsed period pinned to its record."""
        return self._solve(
            problem, optimization_run_id, frozen_periods=frozen_periods, forced_ids=()
        )

    def solve_forced(
        self,
        problem: OptimizationProblem,
        optimization_run_id: UUID,
        forced_behavior_ids: Sequence[UUID],
        frozen_periods: Optional[Dict[int, Dict[int, int]]] = None,
    ) -> OptimizationSolution:
        """Force *forced_behavior_ids* into the plan, declining others if needed."""
        return self._solve(
            problem,
            optimization_run_id,
            frozen_periods=frozen_periods,
            forced_ids={str(b) for b in forced_behavior_ids},
            solver_name="candidate_forced",
        )

    # -- internals -------------------------------------------------------

    def _solve(
        self,
        problem: OptimizationProblem,
        optimization_run_id: UUID,
        frozen_periods: Optional[Dict[int, Dict[int, int]]],
        forced_ids: Set[str],
        solver_name: Optional[str] = None,
    ) -> OptimizationSolution:
        started = time.perf_counter()
        partial = frozen_periods is not None
        frozen_periods = frozen_periods or {}
        forced = forced_ids

        if len(problem.behaviors) > MAX_BEHAVIORS:
            raise SolverError(
                f"This plan has {len(problem.behaviors)} active behaviours; the planner "
                f"accepts up to {MAX_BEHAVIORS}. Deactivate some, or split the day."
            )

        periods = problem.time_periods
        all_frozen = {t for pins in frozen_periods.values() for t in pins}
        earliest_free = max(all_frozen) + 1 if all_frozen else 0

        frozen_items: List[ScheduleItem] = []
        frozen_minutes: Dict[int, int] = {}
        for b_idx, pins in frozen_periods.items():
            if b_idx >= len(problem.behaviors):
                continue
            behavior = problem.behaviors[b_idx]
            done = [t for t, value in pins.items() if value]
            frozen_minutes[b_idx] = len(done) * MINUTES_PER_PERIOD
            for start, length in _frozen_runs(done):
                frozen_items.append(
                    ScheduleItem(
                        behavior_id=behavior.id,
                        behavior_name=behavior.name,
                        time_period=start,
                        scheduled_duration=length * MINUTES_PER_PERIOD,
                        is_scheduled=True,
                    )
                )

        # -- candidates ---------------------------------------------------
        windows: Dict[int, List[Window]] = {}
        candidates: Dict[int, List[Tuple[int, int]]] = {}
        for b_idx, behavior in enumerate(problem.behaviors):
            windows[b_idx] = contiguous_ranges(
                periods_for_time_slots(list(behavior.preferred_time_slots)), periods
            )
            remaining_min = max(0, behavior.min_duration - frozen_minutes.get(b_idx, 0))
            remaining_max = max(0, behavior.max_duration - frozen_minutes.get(b_idx, 0))
            candidates[b_idx] = generate_candidates(
                windows[b_idx], remaining_min, remaining_max, earliest_free, periods
            )

        eligible = [
            b_idx
            for b_idx, behavior in enumerate(problem.behaviors)
            if behavior.min_duration > 0
        ]

        for b_idx in eligible:
            if str(problem.behaviors[b_idx].id) in forced and not candidates[b_idx]:
                raise InfeasibleProblemError(
                    f"'{problem.behaviors[b_idx].name}' cannot be added: no free "
                    "window is long enough for any allowed duration"
                )

        if not eligible:
            return self._build_solution(
                problem,
                optimization_run_id,
                solver_name or ("candidate_partial" if partial else "candidate"),
                frozen_items,
                [],
                diagnostics={"declines": [], "candidate_count": 0},
                started=started,
                frozen_periods=all_frozen,
                partial=partial,
            )

        lp = pulp.LpProblem("candidate_placement", pulp.LpMaximize)
        y: Dict[Tuple[int, int], pulp.LpVariable] = {}
        z: Dict[int, pulp.LpVariable] = {}

        for b_idx in eligible:
            for index in range(len(candidates[b_idx])):
                y[(b_idx, index)] = pulp.LpVariable(f"y_{b_idx}_{index}", cat="Binary")
            z[b_idx] = pulp.LpVariable(f"z_{b_idx}", cat="Binary")

        objective = []
        for b_idx in eligible:
            behavior = problem.behaviors[b_idx]
            score = _score(behavior, problem.objectives)
            for index, (_start, length) in enumerate(candidates[b_idx]):
                objective.append(y[(b_idx, index)] * length * MINUTES_PER_PERIOD * score)
            penalty = max(0.0, score) * behavior.min_duration + DECLINE_TIE_BREAK
            objective.append(-z[b_idx] * penalty)
        lp += pulp.lpSum(objective)

        by_period: Dict[int, List[pulp.LpVariable]] = {}
        for b_idx in eligible:
            for index, (start, length) in enumerate(candidates[b_idx]):
                for period in range(start, start + length):
                    by_period.setdefault(period, []).append(y[(b_idx, index)])
        for period, variables in by_period.items():
            lp += pulp.lpSum(variables) <= 1, f"exclusive_{period}"

        for b_idx in eligible:
            behavior = problem.behaviors[b_idx]
            selected = pulp.lpSum(y[(b_idx, i)] for i in range(len(candidates[b_idx])))
            # Scheduled or explicitly declined, never both and never neither.
            lp += selected + z[b_idx] <= 1, f"scheduled_not_declined_{b_idx}"
            lp += selected + z[b_idx] >= 1, f"declined_not_forgotten_{b_idx}"
            if str(behavior.id) in forced:
                lp += z[b_idx] == 0, f"forced_{b_idx}"
                lp += selected == 1, f"forced_count_{b_idx}"
            elif not candidates[b_idx]:
                lp += z[b_idx] == 1, f"no_candidate_{b_idx}"

        # -- constraints ---------------------------------------------------
        for constraint in problem.active_constraints:
            params = constraint.parameters

            if constraint.type == "time_budget":
                limit = params.get("max_daily_minutes", 480)
                scheduled_frozen = sum(frozen_minutes.values())
                lp += (
                    pulp.lpSum(
                        y[(b_idx, index)] * length
                        for b_idx in eligible
                        for index, (_start, length) in enumerate(candidates[b_idx])
                    )
                    * MINUTES_PER_PERIOD
                    <= limit - scheduled_frozen,
                    "time_budget",
                )

            elif constraint.type == "frequency":
                behavior_id = params.get("behavior_id")
                min_freq = params.get("min_frequency", 0)
                max_freq = params.get("max_frequency", periods)
                try:
                    b_idx = next(
                        i for i, b in enumerate(problem.behaviors) if str(b.id) == str(behavior_id)
                    )
                except StopIteration:
                    continue
                if b_idx not in eligible:
                    continue
                done = frozen_minutes.get(b_idx, 0) // MINUTES_PER_PERIOD
                block_periods = pulp.lpSum(
                    y[(b_idx, index)] * length
                    for index, (_start, length) in enumerate(candidates[b_idx])
                )
                remaining_min = max(0, min_freq - done)
                remaining_max = max(0, max_freq - done)
                if remaining_min > 0:
                    lp += block_periods >= remaining_min, f"min_freq_{behavior_id}"
                if remaining_max > 0:
                    lp += block_periods <= remaining_max, f"max_freq_{behavior_id}"

        try:
            status = lp.solve(pulp.PULP_CBC_CMD(timeLimit=self.timeout_seconds, msg=0))
        except Exception as exc:  # pragma: no cover - defensive
            raise SolverError("Solver encountered an unexpected error") from exc
        status_name = pulp.LpStatus[status]

        if status_name == "Infeasible":
            raise InfeasibleProblemError(
                "No plan satisfies the current constraints"
                + (" with the elapsed sessions frozen" if partial else "")
            )
        if status_name == "Unbounded":
            raise SolverError("The problem is unbounded")
        if status_name != "Optimal" and not self.accept_nonoptimal:
            raise SolverTimeoutError(
                f"Solver did not reach optimality within {self.timeout_seconds} seconds"
            )
        if status_name != "Optimal":
            # A time-limited run leaves relaxation values behind; that is not a plan.
            raise SolverError(
                "Solver did not reach optimality; refusing to build a plan from a relaxation"
            )

        sessions: List[ScheduleItem] = []
        names = {b.id: b.name for b in problem.behaviors}
        for b_idx in eligible:
            for index, (start, length) in enumerate(candidates[b_idx]):
                value = y[(b_idx, index)].value()
                if value and value > 0.5:
                    behavior = problem.behaviors[b_idx]
                    sessions.append(
                        ScheduleItem(
                            behavior_id=behavior.id,
                            behavior_name=behavior.name,
                            time_period=start,
                            scheduled_duration=length * MINUTES_PER_PERIOD,
                            is_scheduled=True,
                        )
                    )

        occupied = {
            item.time_period + offset
            for item in sessions
            for offset in range(item.scheduled_duration // MINUTES_PER_PERIOD)
        }
        free_periods = set(range(periods)) - occupied - set(all_frozen)
        declined = []
        for b_idx in eligible:
            value = z[b_idx].value()
            if not value or value <= 0.5:
                continue
            behavior = problem.behaviors[b_idx]
            declined.append(
                {
                    "behaviorId": str(behavior.id),
                    "behaviorName": names[behavior.id],
                    "reason": self._decline_reason(
                        candidates[b_idx], free_periods, windows[b_idx]
                    ),
                }
            )

        diagnostics = {
            "solver_status": status_name,
            "solve_status": SolveStatus.OPTIMAL.value,
            "candidate_count": len(y),
            "declines": declined,
            "declines_count": len(declined),
            "objective_weights": dict(problem.objectives),
            "solver_objective": round(float(lp.objective.value() or 0.0), 4),
            "formulation": "candidate",
        }
        if forced:
            diagnostics["forced_behavior_ids"] = sorted(forced)
        if partial:
            diagnostics["frozen_periods_count"] = len(all_frozen)
            diagnostics["earliest_free_period"] = earliest_free

        return self._build_solution(
            problem,
            optimization_run_id,
            solver_name or ("candidate_partial" if partial else "candidate"),
            frozen_items,
            sessions,
            diagnostics=diagnostics,
            started=started,
            frozen_periods=all_frozen,
            partial=partial,
        )

    @staticmethod
    def _decline_reason(
        candidates: List[Tuple[int, int]],
        free_periods: Set[int],
        windows: Sequence[Window],
    ) -> str:
        """Why a behaviour is not in the plan.

        Nothing outranks a behaviour in this formulation (there is no protected
        tier), so a decline is always either "no allowed duration fits the free
        room" or "the day had no room at all".
        """
        if not candidates:
            return "no_fit"
        if any(
            all(period in free_periods for period in range(start, start + length))
            for start, length in candidates
        ):
            # A candidate fits in periods nobody took; the objective ranked its
            # value below the decline cost, i.e. its net value was not positive.
            return "no_fit"
        if not windows:
            return "no_fit"
        return "over_capacity"

    def _build_solution(
        self,
        problem: OptimizationProblem,
        optimization_run_id: UUID,
        solver_name: str,
        frozen_items: Sequence[ScheduleItem],
        sessions: Sequence[ScheduleItem],
        *,
        diagnostics: Dict,
        started: float,
        frozen_periods: Set[int],
        partial: bool,
    ) -> OptimizationSolution:
        items = sorted(
            list(frozen_items) + list(sessions), key=lambda item: item.time_period
        )

        violations = validate_schedule(problem, items)
        if violations:
            raise SolverError(
                "Solver produced a schedule that fails validation: "
                + "; ".join(violations[:5])
            )

        behaviors_by_id = {b.id: b for b in problem.behaviors}
        total_value = compute_total(problem.objectives, behaviors_by_id, items)
        contributions = build_contributions(problem.objectives, behaviors_by_id, items)

        diagnostics = dict(diagnostics)
        diagnostics.setdefault("solver_status", "Optimal")
        diagnostics.setdefault("solve_status", SolveStatus.OPTIMAL.value)
        diagnostics["session_count"] = len([i for i in items if i.is_scheduled])
        diagnostics["plan_value"] = total_value

        return OptimizationSolution(
            optimization_run_id=optimization_run_id,
            status=SolveStatus.OPTIMAL.value,
            solver=solver_name,
            total_objective_value=total_value,
            schedule_items=items,
            objective_contributions=contributions,
            execution_time_seconds=round(time.perf_counter() - started, 4),
            diagnostics=diagnostics,
        )
