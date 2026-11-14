"""Like-for-like comparison: candidate model with declines disabled.

Both models must schedule every behaviour (one session each for the candidate
model). Under equal constraints the block model's feasible region is larger — it
may split a behaviour across blocks — so its objective must be >= the candidate's.
Any case where the candidate is higher is a bug in the comparison or in one of the
models, and is printed as such.

    uv run python tools/like_for_like.py
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "backend")))

import bench_cbc  # noqa: E402
from bench_candidate_v2 import to_prototype  # noqa: E402
from candidate_model import PlanTooLargeError, solve  # noqa: E402

WEIGHTS = {"health": 0.6, "productivity": 0.4}


def main() -> None:
    rows = []
    violations = []
    print(f"{'instance':<24} {'block':<22} {'block obj':>10} {'cand status':<12} "
          f"{'cand obj':>10} {'delta':>10}")

    for n in bench_cbc.SIZES:
        for duration_mode in ("fixed", "variable"):
            for window_mode in ("narrow", "wide"):
                base = bench_cbc.run_case(n, duration_mode, window_mode)
                problem = bench_cbc.build_problem(n, duration_mode, window_mode)
                prototype_behaviors = to_prototype(problem)
                try:
                    cand = solve(prototype_behaviors, WEIGHTS, force_all=True)
                    cand_status = cand.status
                    cand_objective = round(cand.objective, 3) if cand.status == "optimal" else None
                except PlanTooLargeError as exc:
                    cand_status, cand_objective = "refused", None
                    _ = str(exc)

                delta = None
                if base["objective"] is not None and cand_objective is not None:
                    delta = round(cand_objective - base["objective"], 3)
                    if delta > 1e-6:
                        violations.append(
                            {
                                "instance": f"{n} {duration_mode} {window_mode}",
                                "block": base["objective"],
                                "candidate": cand_objective,
                                "delta": delta,
                            }
                        )

                row = {
                    "instance": f"{n} {duration_mode} {window_mode}",
                    "block_status": base["status"],
                    "block_objective": base["objective"],
                    "candidate_status": cand_status,
                    "candidate_objective": cand_objective,
                    "candidate_minus_block": delta,
                }
                rows.append(row)
                print(
                    f"{row['instance']:<24} {str(row['block_status']):<22} "
                    f"{str(row['block_objective']):>10} {cand_status:<12} "
                    f"{str(cand_objective):>10} {str(delta):>10}"
                )

    print(f"\ncases where candidate > block: {len(violations)}")
    for violation in violations:
        print("  VIOLATION", json.dumps(violation))

    path = os.path.join(HERE, "like_for_like_results.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"rows": rows, "violations": violations}, handle, indent=2)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
