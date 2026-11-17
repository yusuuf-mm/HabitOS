"""One-off probe v5: set cover (large integrality gap) under short CBC limits.

Not committed. Run: uv run python ../scratch/timeout_probe5.py
"""

from __future__ import annotations

import json
import random

import pulp
from pulp import LpMinimize, LpProblem, LpStatus, LpVariable, PULP_CBC_CMD, lpSum


def run(n_sets, n_elements, density, limit, seed=23):
    rng = random.Random(seed)
    cover = [[] for _ in range(n_elements)]
    for s in range(n_sets):
        for e in rng.sample(range(n_elements), density):
            cover[e].append(s)
    # keep only elements that at least one set can cover
    cover = [c for c in cover if c]

    prob = LpProblem(f"setcover_{n_sets}_{limit}", LpMinimize)
    x = [LpVariable(f"x_{n_sets}_{s}", cat="Binary") for s in range(n_sets)]
    prob += lpSum(x)
    for i, sets in enumerate(cover):
        prob += lpSum(x[s] for s in sets) >= 1, f"cover_{i}"

    prob.solve(PULP_CBC_CMD(timeLimit=limit, msg=0))
    chosen = sum(1 for v in x if v.varValue and v.varValue > 0.5)
    # verify legality of the reported values
    legal = all(sum(v.varValue or 0 for v in [x[s] for s in sets]) >= 0.999 for sets in cover)
    return {
        "n_sets": n_sets,
        "n_elements": len(cover),
        "time_limit": limit,
        "pulp_status": prob.status,
        "pulp_status_text": LpStatus[prob.status],
        "sol_status": prob.sol_status,
        "sol_status_text": pulp.LpSolution[prob.sol_status],
        "objective": prob.objective.value() if prob.objective is not None else None,
        "chosen_sets": chosen,
        "values_cover_all_elements": legal,
    }


def main():
    cases = [
        run(600, 900, 4, 0.5),
        run(1200, 1800, 5, 0.5),
        run(1200, 1800, 5, 2.0),
    ]
    print(json.dumps({"pulp_version": pulp.__version__, "cases": cases}, indent=2))


if __name__ == "__main__":
    main()
