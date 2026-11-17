"""One-off probe v4: hard multi-dimensional knapsacks at short CBC time limits.

Not committed. Run: uv run python ../scratch/timeout_probe4.py
"""

from __future__ import annotations

import json
import random

import pulp
from pulp import LpMaximize, LpProblem, LpStatus, LpVariable, PULP_CBC_CMD, lpSum


def run(n, limit, dims=3, seed=17):
    rng = random.Random(seed)
    weights = [[rng.randint(80, 100) for _ in range(n)] for _ in range(dims)]
    values = [weights[0][i] + 37 for i in range(n)]  # strongly correlated
    prob = LpProblem(f"mkp_{n}_{limit}", LpMaximize)
    x = [LpVariable(f"x_{n}_{i}", cat="Binary") for i in range(n)]
    prob += lpSum(values[i] * x[i] for i in range(n))
    for d in range(dims):
        prob += lpSum(weights[d][i] * x[i] for i in range(n)) <= int(sum(weights[d]) * 0.5)
    prob.solve(PULP_CBC_CMD(timeLimit=limit, msg=0))
    nonzero = sum(1 for v in x if v.varValue and v.varValue > 0.5)
    return {
        "n": n,
        "dims": dims,
        "time_limit": limit,
        "pulp_status": prob.status,
        "pulp_status_text": LpStatus[prob.status],
        "sol_status": prob.sol_status,
        "sol_status_text": pulp.LpSolution[prob.sol_status],
        "objective": prob.objective.value() if prob.objective is not None else None,
        "selected_items": nonzero,
    }


def main():
    cases = []
    for n in (2000, 4000, 8000):
        for limit in (0.1, 0.5):
            cases.append(run(n, limit))
    print(json.dumps({"pulp_version": pulp.__version__, "cases": cases}, indent=2))


if __name__ == "__main__":
    main()
