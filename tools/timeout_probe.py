"""One-off probe: force real CBC timeouts in PuLP 2.8.0 and record what the API reports.

Not committed. Run: uv run python ../scratch/timeout_probe.py
"""

from __future__ import annotations

import json
import random

import pulp
from pulp import LpMaximize, LpProblem, LpStatus, LpVariable, PULP_CBC_CMD, lpSum


def describe(problem, elapsed_label):
    vars_with_value = [v for v in problem.variables() if v.varValue is not None]
    return {
        "moment": elapsed_label,
        "pulp_status": problem.status,
        "pulp_status_text": LpStatus[problem.status],
        "sol_status": problem.sol_status,
        "sol_status_text": pulp.LpSolution[problem.sol_status],
        "objective": problem.objective.value() if problem.objective is not None else None,
        "variables_with_value": len(vars_with_value),
        "total_variables": len(problem.variables()),
    }


def no_incumbent_case():
    """Hard 0-1 knapsack: force a limit so short that CBC cannot finish a first incumbent."""
    rng = random.Random(7)
    n = 4000
    weights = [rng.randint(40, 100) for _ in range(n)]
    values = [rng.randint(1, 100) for _ in range(n)]
    capacity = sum(weights) // 3
    prob = LpProblem("no_incumbent", LpMaximize)
    x = [LpVariable(f"x{i}", cat="Binary") for i in range(n)]
    prob += lpSum(values[i] * x[i] for i in range(n))
    prob += lpSum(weights[i] * x[i] for i in range(n)) <= capacity
    # Extra coupling constraints to slow the first feasible solution.
    for k in range(0, n - 50, 50):
        prob += lpSum(x[k : k + 50]) <= 24
    prob.solve(PULP_CBC_CMD(timeLimit=0.05, msg=0))
    return describe(prob, "timeLimit=0.05")


def incumbent_case():
    """Same shape, longer limit: CBC returns an incumbent without proving optimality."""
    rng = random.Random(11)
    n = 1200
    weights = [rng.randint(40, 100) for _ in range(n)]
    values = [rng.randint(1, 100) for _ in range(n)]
    capacity = sum(weights) // 2
    prob = LpProblem("with_incumbent", LpMaximize)
    x = [LpVariable(f"y{i}", cat="Binary") for i in range(n)]
    prob += lpSum(values[i] * x[i] for i in range(n))
    prob += lpSum(weights[i] * x[i] for i in range(n)) <= capacity
    for k in range(0, n - 40, 40):
        prob += lpSum(x[k : k + 40]) >= 3
    prob.solve(PULP_CBC_CMD(timeLimit=1.0, msg=0))
    return describe(prob, "timeLimit=1.0")


def main():
    out = {"pulp_version": pulp.__version__, "cases": []}
    for fn in (no_incumbent_case, incumbent_case):
        try:
            out["cases"].append(fn())
        except Exception as exc:  # record the real failure, don't hide it
            out["cases"].append({"probe": fn.__name__, "error": f"{type(exc).__name__}: {exc}"})
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
