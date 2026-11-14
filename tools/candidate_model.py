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
    objective: float
    sessions: list[Session] = field(default_factory=list)
    declined: list[Decline] = field(default_factory=list)
    seconds: float = 0.0
    variables: int = 0


def generate_candidates(behavior: Behavior, periods: int = PERIODS_PER_DAY) -> list[tuple[int, int]]:
    """Every contiguous run inside one window whose length is within the bounds."""
    lo = max(1, math.ceil(behavior.min_duration / MINUTES_PER_PERIOD))
    hi = max(lo, math.floor(behavior.max_duration / MINUTES_PER_PERIOD))
    out: list[tuple[int, int]] = []
    for window_start, window_end in behavior.windows:
        window_start = max(0, window_start)
        window_end = min(periods, window_end)
        for length in range(lo, hi + 1):
            for start in range(window_start, window_end - length + 1):
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
) -> Solution:
    """Solve the candidate-placement model. `frozen` maps period -> 0/1."""
    started = time.perf_counter()
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
        lp += selected + z[behavior.id] <= limit, f"one_or_decline_{behavior.id}"
        if not candidates[behavior.id]:
            # Nothing fits at all: the behaviour is declined and reported, never
            # silently dropped from the model.
            lp += z[behavior.id] == 1, f"no_candidate_{behavior.id}"
        elif behavior.protected:
            # Protected behaviours are scheduled or explicitly declined, never
            # silently skipped (docs/FORMULATION.md, constraint 3).
            lp += selected + z[behavior.id] == limit, f"protected_{behavior.id}"

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

    value = sum(
        session.duration * next(b for b in eligible if b.id == session.behavior_id).score(weights)
        for session in sessions
    ) - sum(
        protected_penalty
        for decline in declined
        if any(b.id == decline.behavior_id and b.protected for b in eligible)
    )

    return Solution(
        status="optimal",
        objective=value,
        sessions=sorted(sessions, key=lambda s: s.start),
        declined=declined,
        seconds=seconds,
        variables=len(y),
    )
