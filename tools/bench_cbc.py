"""One-off measured benchmark of the candidate-placement MILP (96 binary periods).

Not committed. Run: uv run python ../scratch/bench_cbc.py
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
from datetime import date
from uuid import uuid4

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "backend")))

from app.core.constants import periods_for_time_slots  # noqa: E402
from app.optimization.models import (  # noqa: E402
    BehaviorScheduleInput,
    OptimizationProblem,
)
from app.optimization.solvers.linear import LinearSolver  # noqa: E402

WINDOWS = {
    "narrow": ["morning"],  # 07:00-12:00, 300 min of capacity
    "wide": ["flexible"],  # 05:00-24:00, 1140 min of capacity
}
SIZES = (10, 20, 40)


def build_problem(n: int, duration_mode: str, window_mode: str) -> OptimizationProblem:
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
    return OptimizationProblem(
        user_id=uuid4(),
        behaviors=behaviours,
        objectives={"health": 0.6, "productivity": 0.4},
        constraints=[],
        start_date=date.today(),
        end_date=date.today(),
        time_periods=96,
    )


def run_case(n: int, duration_mode: str, window_mode: str, timeout: int = 60) -> dict:
    problem = build_problem(n, duration_mode, window_mode)
    solver = LinearSolver(timeout_seconds=timeout)
    started = time.perf_counter()
    try:
        solution = solver.solve(problem, uuid4())
        elapsed = time.perf_counter() - started
        return {
            "behaviours": n,
            "durations": duration_mode,
            "windows": window_mode,
            "capacity_min": len(periods_for_time_slots(WINDOWS[window_mode])) * 15,
            "status": solution.status,
            "solver_status": (solution.diagnostics or {}).get("solver_status"),
            "objective": solution.total_objective_value,
            "sessions": len(solution.schedule_items),
            "elapsed_s": round(elapsed, 3),
        }
    except Exception as exc:  # infeasibility is a measurement too
        elapsed = time.perf_counter() - started
        return {
            "behaviours": n,
            "durations": duration_mode,
            "windows": window_mode,
            "capacity_min": len(periods_for_time_slots(WINDOWS[window_mode])) * 15,
            "status": type(exc).__name__,
            "solver_status": None,
            "objective": None,
            "sessions": None,
            "elapsed_s": round(elapsed, 3),
        }


def main() -> None:
    results = []
    for n in SIZES:
        for duration_mode in ("fixed", "variable"):
            for window_mode in ("narrow", "wide"):
                case = run_case(n, duration_mode, window_mode)
                results.append(case)
                print(json.dumps(case), flush=True)
    print("\nSUMMARY")
    print(f"{'n':>3} {'durations':<9} {'windows':<7} {'cap':>5} {'status':<22} {'obj':>8} {'sessions':>8} {'seconds':>8}")
    for r in results:
        print(
            f"{r['behaviours']:>3} {r['durations']:<9} {r['windows']:<7} {r['capacity_min']:>5} "
            f"{str(r['status']):<22} {str(r['objective']):>8} {str(r['sessions']):>8} {r['elapsed_s']:>8}"
        )
    with open(os.path.join(HERE, "bench_cbc_results.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)


if __name__ == "__main__":
    main()
