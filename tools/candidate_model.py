"""Candidate-placement prototype — see docs/FORMULATION.md.

One binary per candidate session instead of one per (behaviour, period), so a
selected session is contiguous by construction and multi-session behaviours are
explicit slots with a minimum gap.

Not imported by production code. `tools/bench_candidate_v2.py` and
`backend/tests/test_candidate_model.py` are the only callers.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Iterable, Sequence

import pulp

MINUTES_PER_PERIOD = 15
PERIODS_PER_DAY = 96
# A plan is capped so the candidate set stays solvable to optimality in a
# synchronous request (see docs/FORMULATION.md §Size limits).
MAX_BEHAVIORS = 25
MAX_DURATION_OPTIONS = 8
ALIGN_PERIODS = 2  # 30 minutes


@dataclass
class Behavior:
    id: str
    name: str
    min_duration: int
    max_duration: int
    impacts: dict[str, float]
    windows: Sequence[tuple[int, int]]  # half-open period ranges
    protected: bool = False
    sessions: int = 1
    min_gap: int = 0  # minutes between two sessions of the same behaviour

    def score(self, weights: dict[str, float]) -> float:
        return sum(self.impacts.get(key, 0.0) * weight for key, weight in weights.items())


@dataclass
class Session:
    behavior_id: str
    behavior_name: str
    start: int
    duration: int


@dataclass
class Decline:
    behavior_id: str
    behavior_name: str
    reason: str  # no_fit | preempted_by_protected | over_capacity


@dataclass
class Solution:
    status: str
    # Placement value of the *emitted* sessions: the single user-facing
    # definition (the Phase 1 `objective.py` quantity).
    objective: float
    sessions: list[Session] = field(default_factory=list)
    declined: list[Decline] = field(default_factory=list)
    seconds: float = 0.0
    variables: int = 0
    # The penalised quantity the solver actually maximised (decline penalties
    # included). Diagnostics only; never shown to users as the plan's value.
    solver_objective: float | None = None
    refused: str | None = None


class PlanTooLargeError(ValueError):
    """Raised above MAX_BEHAVIORS; a plan is never silently truncated."""


def duration_options(behavior: Behavior) -> list[int]:
    """At most MAX_DURATION_OPTIONS candidate lengths, always including max."""
    lo = max(1, math.ceil(behavior.min_duration / MINUTES_PER_PERIOD))
    hi = max(lo, math.floor(behavior.max_duration / MINUTES_PER_PERIOD))
    count = hi - lo + 1
    if count <= MAX_DURATION_OPTIONS:
        return list(range(lo, hi + 1))
    step = math.ceil((count - 1) / (MAX_DURATION_OPTIONS - 1))
    options = list(range(lo, hi + 1, step))
    if options[-1] != hi:
        options[-1] = hi
    return options


def generate_candidates(behavior: Behavior, periods: int = PERIODS_PER_DAY) -> list[tuple[int, int]]:
    """Every contiguous run inside one window whose length is one of the options.

    Starts are aligned to 30 minutes when the duration is a multiple of 30 minutes;
    an odd number of periods keeps every start, because aligning it would move the
    end off the half hour instead.
    """
    out: list[tuple[int, int]] = []
    for window_start, window_end in behavior.windows:
        window_start = max(0, window_start)
        window_end = min(periods, window_end)
        for length in duration_options(behavior):
            step = ALIGN_PERIODS if length % ALIGN_PERIODS == 0 else 1
            first = window_start if window_start % step == 0 else window_start + 1
            for start in range(first, window_end - length + 1, step):
                out.append((start, length))
    return out


def _decline_reason(
    behavior: Behavior,
    candidates: list[tuple[int, int]],
    used_by_protected: set[int],
    free_periods: set[int],
) -> str:
    if behavior.protected:
        # Protected demand that did not fit is a capacity failure, never a loss to
        # something else: nothing outranks it.
        return "over_capacity"
    if any(
        all(period in free_periods for period in range(start, start + length))
        for start, length in candidates
    ):
        # A session would fit in periods nobody else took, so the model chose not
        # to take it; report the day as full.
        return "no_fit"
    if any(
        any(period in used_by_protected for period in range(start, start + length))
        for start, length in candidates
    ):
        return "preempted_by_protected"
    return "no_fit"


def solve(
    behaviors: Sequence[Behavior],
    weights: dict[str, float],
    periods: int = PERIODS_PER_DAY,
    frozen: dict[int, int] | None = None,
    time_limit: int = 30,
    protected_penalty: float = 10_000.0,
    allow_decline: bool = True,
    force_all: bool = False,
) -> Solution:
    """Solve the candidate-placement model. `frozen` maps period -> 0/1.

    `force_all` removes the decline option, for like-for-like comparisons: every
    behaviour must be scheduled or the instance is infeasible. It is not a
    user-facing mode.
    """
    started = time.perf_counter()
    if len(behaviors) > MAX_BEHAVIORS:
        raise PlanTooLargeError(
            f"This plan has {len(behaviors)} active behaviours; the planner accepts "
            f"up to {MAX_BEHAVIORS}. Deactivate some, or split the day."
        )
    frozen = frozen or {}
    eligible = [b for b in behaviors if b.min_duration > 0]
    candidates = {b.id: generate_candidates(b, periods) for b in eligible}

    # Frozen periods are already decided: no candidate may touch them.
    def usable(candidate: tuple[int, int]) -> bool:
        start, length = candidate
        return all(period not in frozen for period in range(start, start + length))

    for key in list(candidates):
        candidates[key] = [c for c in candidates[key] if usable(c)]

    if not eligible:
        return Solution("optimal", 0.0, seconds=time.perf_counter() - started)

    lp = pulp.LpProblem("candidate_placement", pulp.LpMaximize)
    y: dict[tuple[str, int], pulp.LpVariable] = {}
    z: dict[str, pulp.LpVariable] = {}

    for behavior in eligible:
        for index, _candidate in enumerate(candidates[behavior.id]):
            y[(behavior.id, index)] = pulp.LpVariable(
                f"y_{behavior.id}_{index}", cat="Binary"
            )
        z[behavior.id] = pulp.LpVariable(f"z_{behavior.id}", cat="Binary")

    objective = []
    for behavior in eligible:
        score = behavior.score(weights)
        for index, (start, length) in enumerate(candidates[behavior.id]):
            objective.append(y[(behavior.id, index)] * length * MINUTES_PER_PERIOD * score)
        objective.append(-z[behavior.id] * (protected_penalty if behavior.protected else 0.0))
    lp += pulp.lpSum(objective)

    by_period: dict[int, list[pulp.LpVariable]] = {}
    for behavior in eligible:
        for index, (start, length) in enumerate(candidates[behavior.id]):
            for period in range(start, start + length):
                by_period.setdefault(period, []).append(y[(behavior.id, index)])
    for period, variables in by_period.items():
        lp += pulp.lpSum(variables) <= 1, f"exclusive_{period}"

    for behavior in eligible:
        selected = pulp.lpSum(y[(behavior.id, i)] for i in range(len(candidates[behavior.id])))
        limit = max(1, behavior.sessions)
        # Every behaviour is either scheduled or explicitly declined. A "both
        # zero" slack would let the model silently forget a behaviour, and a
        # multi-session behaviour could be scheduled *and* declined at once.
        lp += selected + z[behavior.id] * limit <= limit, f"scheduled_not_declined_{behavior.id}"
        lp += selected + z[behavior.id] >= 1, f"declined_not_forgotten_{behavior.id}"
        if force_all:
            lp += z[behavior.id] == 0, f"forced_{behavior.id}"
            lp += selected == limit, f"forced_count_{behavior.id}"
        elif not candidates[behavior.id]:
            lp += z[behavior.id] == 1, f"no_candidate_{behavior.id}"

        if behavior.min_gap > 0 and behavior.sessions > 1:
            entries = candidates[behavior.id]
            for i, (start_a, length_a) in enumerate(entries):
                for j in range(i + 1, len(entries)):
                    start_b, _length_b = entries[j]
                    end_a_minutes = (start_a + length_a) * MINUTES_PER_PERIOD
                    if (start_b * MINUTES_PER_PERIOD) - end_a_minutes < behavior.min_gap:
                        lp += (
                            y[(behavior.id, i)] + y[(behavior.id, j)] <= 1,
                            f"gap_{behavior.id}_{i}_{j}",
                        )

    solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=time_limit)
    status_code = lp.solve(solver)
    seconds = time.perf_counter() - started

    if pulp.LpStatus[status_code] != "Optimal":
        return Solution(
            status=pulp.LpStatus[status_code],
            objective=float("nan"),
            seconds=seconds,
            variables=len(y),
            solver_objective=None,
        )

    sessions: list[Session] = []
    for behavior in eligible:
        for index, (start, length) in enumerate(candidates[behavior.id]):
            if y[(behavior.id, index)].value() and y[(behavior.id, index)].value() > 0.5:
                sessions.append(
                    Session(
                        behavior_id=behavior.id,
                        behavior_name=behavior.name,
                        start=start,
                        duration=length * MINUTES_PER_PERIOD,
                    )
                )

    used_by_protected: set[int] = set()
    for behavior in eligible:
        if not behavior.protected:
            continue
        for session in sessions:
            if session.behavior_id == behavior.id:
                used_by_protected.update(
                    range(session.start, session.start + session.duration // MINUTES_PER_PERIOD)
                )

    occupied: set[int] = set()
    for session in sessions:
        occupied.update(range(session.start, session.start + session.duration // MINUTES_PER_PERIOD))
    free = set(range(periods)) - occupied - set(frozen)

    declined: list[Decline] = []
    for behavior in eligible:
        if z[behavior.id].value() and z[behavior.id].value() > 0.5:
            declined.append(
                Decline(
                    behavior_id=behavior.id,
                    behavior_name=behavior.name,
                    reason=_decline_reason(behavior, candidates[behavior.id], used_by_protected, free),
                )
            )

    # The plan's value is the placement value of the emitted sessions only.
    # Decline penalties belong to the solver's objective, reported separately.
    value = sum(
        session.duration * next(b for b in eligible if b.id == session.behavior_id).score(weights)
        for session in sessions
    )

    return Solution(
        status="optimal",
        objective=value,
        sessions=sorted(sessions, key=lambda s: s.start),
        declined=declined,
        seconds=seconds,
        variables=len(y),
        # Reported separately on purpose: the penalised LP value includes decline
        # penalties, so it is not the plan's value.
        solver_objective=float(lp.objective.value() or 0.0),
    )


def validate_plan(
    behaviors: Sequence[Behavior],
    solution: Solution,
    periods: int = PERIODS_PER_DAY,
    frozen: dict[int, int] | None = None,
) -> list[str]:
    """Contract check for an emitted plan. Returns a list of violations.

    Mirrors the rules the production `validate_schedule` enforces, plus the
    window and frozen-period rules that only exist in this model.
    """
    frozen = frozen or {}
    by_id = {behavior.id: behavior for behavior in behaviors}
    violations: list[str] = []
    occupied: dict[int, str] = {}
    counts: dict[str, int] = {behavior.id: 0 for behavior in behaviors}
    last_end: dict[str, int] = {}
    declined = {decline.behavior_id for decline in solution.declined}

    for session in solution.sessions:
        behavior = by_id.get(session.behavior_id)
        if behavior is None:
            violations.append(f"unknown behaviour {session.behavior_id}")
            continue
        if session.duration % MINUTES_PER_PERIOD != 0:
            violations.append(f"{behavior.name}: duration {session.duration} is not a multiple of 15")
        if session.duration < behavior.min_duration:
            violations.append(f"{behavior.name}: {session.duration} min below minimum {behavior.min_duration}")
        if session.duration > behavior.max_duration:
            violations.append(f"{behavior.name}: {session.duration} min above maximum {behavior.max_duration}")

        length = session.duration // MINUTES_PER_PERIOD
        cells = range(session.start, session.start + length)
        for cell in cells:
            if cell in occupied:
                violations.append(f"overlap at period {cell} between {occupied[cell]} and {behavior.name}")
            occupied[cell] = behavior.name
            if cell in frozen:
                violations.append(f"{behavior.name}: planned over frozen period {cell}")
            if cell < 0 or cell >= periods:
                violations.append(f"{behavior.name}: period {cell} outside the day")
        if not any(
            window_start <= session.start and session.start + length <= window_end
            for window_start, window_end in behavior.windows
        ):
            violations.append(f"{behavior.name}: session {session.start}+{length} outside its windows")

        counts[behavior.id] += 1
        if counts[behavior.id] > max(1, behavior.sessions):
            violations.append(f"{behavior.name}: more than {behavior.sessions} sessions")
        if behavior.min_gap > 0 and behavior.id in last_end:
            gap = (session.start - last_end[behavior.id]) * MINUTES_PER_PERIOD
            if gap < behavior.min_gap:
                violations.append(f"{behavior.name}: gap {gap} min below {behavior.min_gap}")
        last_end[behavior.id] = session.start + length

    if counts[behavior.id] > 0 and behavior.id in declined:
        violations.append(f"{behavior.name}: both scheduled and declined")

    for behavior in behaviors:
        if behavior.protected and counts[behavior.id] == 0 and behavior.id not in declined:
            violations.append(f"{behavior.name}: protected behaviour neither scheduled nor declined")

    return violations
