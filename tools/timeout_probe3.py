"""One-off probe v3: the actual 96-period placement MILP under short CBC limits.

Fresh feasible instance per run. Not committed.
Run: uv run python ../scratch/timeout_probe3.py
"""

from __future__ import annotations

import json
import os
import random
import sys

import pulp
from pulp import LpMaximize, LpProblem, LpStatus, LpVariable, PULP_CBC_CMD, lpSum

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")))

from app.core.constants import MINUTES_PER_PERIOD, periods_for_time_slots

PERIODS = 96
N = 40


def build(n_behaviours=N, seed=42):
    """40 behaviours, exact-duration packing into one flexible window (tight, feasible)."""
    rng = random.Random(seed)
    allowed = periods_for_time_slots(["flexible"])
    prob = LpProblem("placement", LpMaximize)
    x = {}
    for b in range(n_behaviours):
        for t in range(PERIODS):
            x[(b, t)] = LpVariable(f"x_{b}_{t}", cat="Binary")

    objectives = {"health": 0.6, "productivity": 0.4}
    impacts = {
        b: {o: round(rng.uniform(0.1, 1.0), 2) for o in objectives} for b in range(n_behaviours)
    }
    durations = [rng.choice([15, 30, 45]) for _ in range(n_behaviours)]

    prob += lpSum(
        w * impacts[b][o] * lpSum(x[(b, t)] for t in range(PERIODS)) * MINUTES_PER_PERIOD
        for o, w in objectives.items()
        for b in range(n_behaviours)
    )

    for t in range(PERIODS):
        prob += lpSum(x[(b, t)] for b in range(n_behaviours)) <= 1, f"excl_{t}"
    for b in range(n_behaviours):
        for t in range(PERIODS):
            if t not in allowed:
                prob += x[(b, t)] == 0, f"pref_{b}_{t}"
        total = lpSum(x[(b, t)] for t in range(PERIODS)) * MINUTES_PER_PERIOD
        prob += total == durations[b], f"exact_{b}"
    return prob, x, durations


def feasible_assignment(x, durations):
    occupied = {}
    per_behaviour = {}
    for (b, t), var in x.items():
        if var.varValue and var.varValue > 0.5:
            if t in occupied:
                return False, f"period {t} double-booked"
            occupied[t] = b
            per_behaviour[b] = per_behaviour.get(b, 0) + 1
    for b, minutes in per_behaviour.items():
        if minutes * MINUTES_PER_PERIOD != durations[b]:
            return False, f"behaviour {b} got {minutes * MINUTES_PER_PERIOD} min, needs {durations[b]}"
    if not per_behaviour:
        return False, "no behaviour scheduled"
    return True, "legal schedule"


def main():
    cases = []
    total_minutes = sum(build()[2])
    for limit in (0.05, 0.1, 0.2, 0.5, 1.0, 3.0):
        prob, x, durations = build()
        prob.solve(PULP_CBC_CMD(timeLimit=limit, msg=0))
        ok, why = feasible_assignment(x, durations)
        cases.append(
            {
                "time_limit": limit,
                "pulp_status": prob.status,
                "pulp_status_text": LpStatus[prob.status],
                "sol_status": prob.sol_status,
                "sol_status_text": pulp.LpSolution[prob.sol_status],
                "objective": prob.objective.value() if prob.objective is not None else None,
                "assignment_is_legal": ok,
                "assignment_note": why,
                "scheduled_minutes": sum(
                    1 for v in x.values() if v.varValue and v.varValue > 0.5
                ) * MINUTES_PER_PERIOD,
            }
        )
    print(
        json.dumps(
            {
                "pulp_version": pulp.__version__,
                "behaviours": N,
                "required_minutes": total_minutes,
                "capacity_minutes": len(periods_for_time_slots(["flexible"])) * MINUTES_PER_PERIOD,
                "cases": cases,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
