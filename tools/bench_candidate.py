"""One-off prototype: candidate-placement MILP vs the block-binary baseline.

Not committed. Run: uv run python ../scratch/bench_candidate.py

Candidate-placement formulation
-------------------------------
Instead of a binary per (behaviour, 15-minute period), each behaviour owns one
binary per *candidate session* — a contiguous run of blocks that fits entirely
inside one of its allowed windows and whose duration is within [min, max].

    y[b, c] = 1  ⟺  behaviour b is placed as candidate c

    Σ_c y[b, c] == 1                         (each behaviour placed exactly once)
    Σ_{c ∋ t} y[b, c] ≤ 1     for each t     (at most one session per block)
    objective: Σ y[b, c] · impact · duration · weight

Contiguity is structural, so sessions come out contiguous by construction, and
the per-block exclusivity matrix is the only coupling.
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
from datetime import date
from uuid import uuid4

import pulp
from pulp import LpMaximize, LpProblem, LpVariable, PULP_CBC_CMD, lpSum

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "backend")))

from app.core.constants import (  # noqa: E402
    MINUTES_PER_PERIOD,
    periods_for_time_slots,
    TIME_SLOT_RANGES,
)
from app.optimization.models import (  # noqa: E402
    BehaviorScheduleInput,
    OptimizationProblem,
)
from app.optimization.solvers.linear import LinearSolver  # noqa: E402

WINDOWS = {
    "narrow": ["morning"],       # 07:00-12:00 → 300 min
    "wide": ["flexible"],        # 05:00-24:00 → 1140 min
}
SIZES = (10, 20, 40)
PERIODS = 96


def build_behaviours(n: int, duration_mode: str, window_mode: str):
    rng = random.Random(f"{n}-{duration_mode}-{window_mode}")
    behaviours = []
    for i in range(n):
        if duration_mode == "fixed":
            lo = hi = 15
        else:
            lo = rng.choice([15, 30, 45])
            hi = lo + rng.choice([15, 30, 45])
        behaviours.append(
            BehaviorScheduleInput(
                id=uuid4(),
                name=f"Behaviour {i}",
                min_duration=lo,
                typical_duration=(lo + hi) // 2,
                max_duration=hi,
                energy_cost=float(rng.randint(1, 8)),
                impacts={
                    "health": round(rng.uniform(0.1, 1.0), 2),
                    "productivity": round(rng.uniform(0.1, 1.0), 2),
                },
                preferred_time_slots=WINDOWS[window_mode],
            )
        )
    return behaviours


def candidate_runs(allowed: set[int], min_d: int, max_d: int):
    """All (start, n_blocks) contiguous runs inside one allowed window."""
    durations = list(range(min_d, max_d + 1, MINUTES_PER_PERIOD))
    blocks = [max(1, d // MINUTES_PER_PERIOD) for d in durations]
    out = []
    for start in sorted(allowed):
        for n_blocks in sorted(set(blocks)):
            span = range(start, start + n_blocks)
            if all(p in allowed for p in span):
                out.append((start, n_blocks * MINUTES_PER_PERIOD))
    return out


def solve_candidates(behaviours, objectives, timeout=60):
    allowed = periods_for_time_slots(WINDOWS_CURRENT)
    prob = LpProblem("candidate_placement", LpMaximize)
    y = {}
    candidates = {}
    for b_idx, behaviour in enumerate(behaviours):
        runs = candidate_runs(
            allowed, behaviour.min_duration, behaviour.max_duration
        )
        candidates[b_idx] = runs
        y[b_idx] = [
            LpVariable(f"y_{b_idx}_{k}", cat="Binary") for k in range(len(runs))
        ]
        prob += lpSum(y[b_idx]) == 1, f"one_{b_idx}"

    # period capacity
    for t in range(PERIODS):
        terms = []
        for b_idx, runs in candidates.items():
            for k, (start, duration) in enumerate(runs):
                n_blocks = duration // MINUTES_PER_PERIOD
                if start <= t < start + n_blocks:
                    terms.append(y[b_idx][k])
        if terms:
            prob += lpSum(terms) <= 1, f"cap_{t}"

    prob += lpSum(
        objectives[o]
        * behaviours[b_idx].impacts.get(o, 0.0)
        * duration
        * y[b_idx][k]
        for b_idx, runs in candidates.items()
        for k, (start, duration) in enumerate(runs)
        for o in objectives
    )

    started = time.perf_counter()
    prob.solve(PULP_CBC_CMD(timeLimit=timeout, msg=0))
    elapsed = time.perf_counter() - started

    placed = []
    for b_idx, runs in candidates.items():
        for k, (start, duration) in enumerate(runs):
            if y[b_idx][k].varValue and y[b_idx][k].varValue > 0.5:
                placed.append({"behaviour": b_idx, "start": start, "duration": duration})
                break
    return {
        "status": pulp.LpStatus[prob.status],
        "objective": round(prob.objective.value(), 3) if prob.objective is not None else None,
        "variables": len(prob.variables()),
        "constraints": len(prob.constraints),
        "sessions": len(placed),
        "seconds": round(elapsed, 3),
        "placed": placed,
    }


def solve_baseline(behaviours, objectives, timeout=60):
    problem = OptimizationProblem(
        user_id=uuid4(),
        behaviors=behaviours,
        objectives=objectives,
        constraints=[],
        start_date=date.today(),
        end_date=date.today(),
        time_periods=PERIODS,
    )
    started = time.perf_counter()
    try:
        solution = LinearSolver(timeout_seconds=timeout).solve(problem, uuid4())
        elapsed = time.perf_counter() - started
        return {
            "status": solution.diagnostics.get("solver_status") if solution.diagnostics else None,
            "objective": solution.total_objective_value,
            "sessions": len(solution.schedule_items),
            "seconds": round(elapsed, 3),
            "variables": len(behaviours) * PERIODS,
            "placed": [
                {
                    "behaviour": i,
                    "start": item.time_period,
                    "duration": item.scheduled_duration,
                }
                for i, item in enumerate(solution.schedule_items)
            ],
        }
    except Exception as exc:
        elapsed = time.perf_counter() - started
        return {
            "status": type(exc).__name__,
            "objective": None,
            "sessions": None,
            "seconds": round(elapsed, 3),
            "variables": len(behaviours) * PERIODS,
            "placed": [],
        }


WINDOWS_CURRENT: list[str] = []


def main():
    global WINDOWS_CURRENT
    results = []
    for n in SIZES:
        for duration_mode in ("fixed", "variable"):
            for window_mode in ("narrow", "wide"):
                behaviours = build_behaviours(n, duration_mode, window_mode)
                objectives = {"health": 0.6, "productivity": 0.4}
                WINDOWS_CURRENT = WINDOWS[window_mode]
                baseline = solve_baseline(behaviours, objectives)
                candidate = solve_candidates(behaviours, objectives)
                row = {
                    "n": n,
                    "durations": duration_mode,
                    "windows": window_mode,
                    "baseline": {k: v for k, v in baseline.items() if k != "placed"},
                    "candidate": {k: v for k, v in candidate.items() if k != "placed"},
                }
                results.append(row)
                print(json.dumps(row), flush=True)

    print("\nSUMMARY  (baseline = block binaries, candidate = candidate-placement)")
    print(
        f"{'n':>3} {'dur':<9} {'win':<7} | {'base status':<22} {'base obj':>9} "
        f"{'base sess':>9} {'base s':>7} | {'cand status':<10} {'cand obj':>9} "
        f"{'cand sess':>9} {'cand s':>7} {'cand vars':>9}"
    )
    for r in results:
        b, c = r["baseline"], r["candidate"]
        print(
            f"{r['n']:>3} {r['durations']:<9} {r['windows']:<7} | "
            f"{str(b['status']):<22} {str(b['objective']):>9} {str(b['sessions']):>9} {b['seconds']:>7} | "
            f"{str(c['status']):<10} {str(c['objective']):>9} {str(c['sessions']):>9} {c['seconds']:>7} {c['variables']:>9}"
        )
    with open(os.path.join(HERE, "bench_candidate_results.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)


if __name__ == "__main__":
    main()
