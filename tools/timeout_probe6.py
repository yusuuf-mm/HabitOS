"""One-off probe v6: force CBC to stop while holding an incumbent.

`maxSolutions 1` stops CBC after its first integer solution, which is the same
"stopped early, has a feasible solution" state a time limit produces.

Not committed. Run: uv run python ../scratch/timeout_probe6.py
"""

from __future__ import annotations

import json
import random

import pulp
from pulp import LpMaximize, LpProblem, LpStatus, LpVariable, PULP_CBC_CMD, lpSum


def run(n, options, limit, seed=31):
    rng = random.Random(seed)
    dims = 3
    weights = [[rng.randint(80, 100) for _ in range(n)] for _ in range(dims)]
    values = [weights[0][i] + 37 for i in range(n)]
    prob = LpProblem(f"stop_{n}", LpMaximize)
    x = [LpVariable(f"z_{n}_{i}", cat="Binary") for i in range(n)]
    prob += lpSum(values[i] * x[i] for i in range(n))
    for d in range(dims):
        prob += lpSum(weights[d][i] * x[i] for i in range(n)) <= int(sum(weights[d]) * 0.5)
    prob.solve(PULP_CBC_CMD(timeLimit=limit, msg=0, options=options))
    chosen = [i for i, v in enumerate(x) if v.varValue and v.varValue > 0.5]
    feasible = all(
        sum(weights[d][i] for i in chosen) <= int(sum(weights[d]) * 0.5) for d in range(dims)
    )
    return {
        "n": n,
        "options": options,
        "time_limit": limit,
        "pulp_status": prob.status,
        "pulp_status_text": LpStatus[prob.status],
        "sol_status": prob.sol_status,
        "sol_status_text": pulp.LpSolution[prob.sol_status],
        "objective": prob.objective.value() if prob.objective is not None else None,
        "chosen_items": len(chosen),
        "chosen_is_feasible": feasible,
    }


def main():
    cases = [
        run(2000, ["maxSolutions 1"], 10),
        run(2000, ["maxSolutions 1", "maxNodes 200"], 10),
        run(2000, [], 0.1),  # plain timeout, for contrast
    ]
    print(json.dumps({"pulp_version": pulp.__version__, "cases": cases}, indent=2))


if __name__ == "__main__":
    main()
