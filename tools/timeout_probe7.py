"""One-off probe v7: set cover at very short limits; compare with the proven optimum.

Not committed. Run: uv run python ../scratch/timeout_probe7.py
"""

from __future__ import annotations

import json
import random

import pulp
from pulp import LpMinimize, LpProblem, LpStatus, LpVariable, PULP_CBC_CMD, lpSum

N_SETS, N_ELEMENTS, DENSITY, SEED = 1200, 1800, 5, 23


def build():
    rng = random.Random(SEED)
    cover = [[] for _ in range(N_ELEMENTS)]
    for s in range(N_SETS):
        for e in rng.sample(range(N_ELEMENTS), DENSITY):
            cover[e].append(s)
    cover = [c for c in cover if c]
    prob = LpProblem("setcover_probe", LpMinimize)
    x = [LpVariable(f"x_{s}", cat="Binary") for s in range(N_SETS)]
    prob += lpSum(x)
    for i, sets in enumerate(cover):
        prob += lpSum(x[s] for s in sets) >= 1, f"cover_{i}"
    return prob, x, cover


def run(limit):
    prob, x, cover = build()
    prob.solve(PULP_CBC_CMD(timeLimit=limit, msg=0))
    chosen = [v for v in x if v.varValue and v.varValue > 0.5]
    covered = all(sum(x[s].varValue or 0 for s in sets) >= 0.999 for sets in cover)
    return {
        "time_limit": limit,
        "pulp_status": prob.status,
        "pulp_status_text": LpStatus[prob.status],
        "sol_status": prob.sol_status,
        "sol_status_text": pulp.LpSolution[prob.sol_status],
        "objective": prob.objective.value() if prob.objective is not None else None,
        "chosen_sets": len(chosen),
        "values_cover_all_elements": covered,
        "integer_valued": all(abs((v.varValue or 0) - round(v.varValue or 0)) < 1e-9 for v in x),
    }


def main():
    cases = [run(0.02), run(0.05), run(0.1), run(0.3)]
    print(json.dumps({"pulp_version": pulp.__version__, "cases": cases}, indent=2))


if __name__ == "__main__":
    main()
