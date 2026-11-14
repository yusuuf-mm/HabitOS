"""Brute-force oracle for the candidate-placement model (docs/FORMULATION.md).

Tiny instances only (about 12 periods, 3 behaviours): every behaviour either
declines or takes one candidate, and every combination is checked for overlap.
The best objective is the ground truth the prototype must match.
"""
from __future__ import annotations

import itertools

from candidate_model import (
    Behavior,
    Decline,
    MINUTES_PER_PERIOD,
    Session,
    Solution,
    generate_candidates,
)

PROTECTED_PENALTY = 10_000.0


def solve_bruteforce(
    behaviors: list[Behavior],
    weights: dict[str, float],
    periods: int = 12,
    frozen: dict[int, int] | None = None,
    protected_penalty: float = PROTECTED_PENALTY,
) -> Solution:
    frozen = frozen or {}
    options = []
    for behavior in behaviors:
        entries = [
            candidate
            for candidate in generate_candidates(behavior, periods)
            if all(period not in frozen for period in range(candidate[0], candidate[0] + candidate[1]))
        ]
        options.append([None] + entries)

    if any(not choices for choices in options):
        # A behaviour with no legal candidate can only decline.
        pass

    best_value = None
    best_choice = None
    for combo in itertools.product(*options):
        occupied: set[int] = set()
        overlap = False
        value = 0.0
        for behavior, choice in zip(behaviors, combo):
            if choice is None:
                if behavior.protected:
                    value -= protected_penalty
                continue
            start, length = choice
            cells = set(range(start, start + length))
            if cells & occupied:
                overlap = True
                break
            occupied |= cells
            value += length * MINUTES_PER_PERIOD * behavior.score(weights)
        if overlap:
            continue
        if best_value is None or value > best_value + 1e-9:
            best_value = value
            best_choice = combo

    if best_choice is None:
        return Solution(status="Infeasible", objective=float("nan"))

    sessions: list[Session] = []
    declined: list[Decline] = []
    for behavior, choice in zip(behaviors, best_choice):
        if choice is None:
            reason = "over_capacity" if behavior.protected else "no_fit"
            declined.append(Decline(behavior.id, behavior.name, reason))
            continue
        start, length = choice
        sessions.append(
            Session(
                behavior_id=behavior.id,
                behavior_name=behavior.name,
                start=start,
                duration=length * MINUTES_PER_PERIOD,
            )
        )

    return Solution(
        status="optimal",
        objective=round(best_value, 6),
        sessions=sorted(sessions, key=lambda session: session.start),
        declined=declined,
    )
