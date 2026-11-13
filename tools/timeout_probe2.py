"""One-off probe v2: find a real CBC timeout that returns an incumbent.

Not committed. Run: uv run python ../scratch/timeout_probe2.py
"""

from __future__ import annotations

import json
import random

import pulp
from pulp import LpMaximize, LpProblem, LpStatus, LpVariable, PULP_CBC_CMD, lpSum


def run_knapsack(label, n, limit, correlated, seed):
    rng = random.Random(seed)
    weights = [rng.randint(80, 100) for _ in range(n)]
    if correlated:
        values = [w + 20 for w in weights]  # strongly correlated: classic hard family
    else:
        values = [rng.randint(1, 100) for _ in range(n)]
    capacity = int(sum(weights) * 0.5)
    prob = LpProblem(label, LpMaximize)
    x = [LpVariable(f"{label}_{i}", cat="Binary") for i in range(n)]
    prob += lpSum(values[i] * x[i] for i in range(n))
    prob += lpSum(weights[i] * x[i] for i in range(n)) <= capacity

    # A second independent knapsack dimension makes the LP bound loose.
    weights2 = [rng.randint(80, 100) for _ in range(n)]
    prob += lpSum(weights2[i] * x[i] for i in range(n)) <= int(sum(weights2) * 0.5)

    prob.solve(PULP_CBC_CMD(timeLimit=limit, msg=0))
    return {
        "label": label,
        "n": n,
        "time_limit": limit,
        "pulp_status": prob.status,
        "pulp_status_text": LpStatus[prob.status],
        "sol_status": prob.sol_status,
        "sol_status_text": pulp.LpSolution[prob.sol_status],
        "objective": prob.objective.value() if prob.objective is not None else None,
        "nonzero_vars": sum(1 for v in prob.variables() if v.varValue),
    }


def main():
    cases = []
    for limit in (0.2, 0.5, 2.0):
        cases.append(run_knapsack(f"corr_{limit}", 2000, limit, True, 3))
    cases.append(run_knapsack("random_0.5", 3000, 0.5, False, 5))
    out = {"pulp_version": pulp.__version__, "cases": cases}
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
