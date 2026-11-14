"""Measured comparison: candidate-placement prototype vs the block model.

Same 12 instances as `bench_cbc.py` (10/20/40 behaviours; fixed/variable
durations; narrow/wide windows), plus three deliberately over-capacity instances.
Run from the repo root:

    uv run python tools/bench_candidate_v2.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from uuid import uuid4

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "backend")))

import bench_cbc  # noqa: E402
from candidate_model import Behavior, MINUTES_PER_PERIOD, PERIODS_PER_DAY, solve  # noqa: E402

from app.core.constants import periods_for_time_slots  # noqa: E402

WEIGHTS = {"health": 0.6, "productivity": 0.4}
WINDOWS = {"narrow": ["morning"], "wide": ["flexible"]}


def to_prototype(problem) -> list[Behavior]:
    out = []
    for index, behavior in enumerate(problem.behaviors):
        windows = []
        for slot in behavior.preferred_time_slots:
            periods = periods_for_time_slots([slot])
            windows.append((min(periods), max(periods) + 1))
        if not windows:
            windows = [(0, PERIODS_PER_DAY)]
        out.append(
            Behavior(
                id=str(index),
                name=behavior.name,
                min_duration=behavior.min_duration,
                max_duration=behavior.max_duration,
                impacts=dict(behavior.impacts),
                windows=windows,
            )
        )
    return out


def over_capacity_instances() -> list[dict]:
    """Three instances the day cannot satisfy; they must be reported, not crash."""
    morning = periods_for_time_slots(["morning"])
    narrow = [(min(morning), max(morning) + 1)]
    wide = [(20, 96)]
    return [
        {
            "name": "15x60min in a 300min window",
            "behaviors": [
                Behavior(
                    id=f"a{i}", name=f"Protected {i}", min_duration=60, max_duration=60,
                    impacts={"health": 1.0}, windows=narrow, protected=True,
                )
                for i in range(15)
            ],
        },
        {
            "name": "40x45min in a 1140min day",
            "behaviors": [
                Behavior(
                    id=f"b{i}", name=f"Flexible {i}", min_duration=45, max_duration=90,
                    impacts={"health": 0.5, "productivity": 0.5}, windows=wide,
                )
                for i in range(40)
            ],
        },
        {
            "name": "12 protected x45min in a 300min window",
            "behaviors": [
                Behavior(
                    id=f"c{i}", name=f"Must-do {i}", min_duration=45, max_duration=45,
                    impacts={"health": 1.0}, windows=narrow, protected=True,
                )
                for i in range(12)
            ],
        },
    ]


def main() -> None:
    rows = []
    print(f"{'instance':<34} {'block status':<22} {'block obj':>10} {'blk sess':>8} {'blk s':>7} "
          f"{'cand obj':>10} {'cand sess':>9} {'cand s':>7} {'declined':>8}")

    for n in bench_cbc.SIZES:
        for duration_mode in ("fixed", "variable"):
            for window_mode in ("narrow", "wide"):
                base = bench_cbc.run_case(n, duration_mode, window_mode)
                problem = bench_cbc.build_problem(n, duration_mode, window_mode)
                protos = to_prototype(problem)
                cand = solve(protos, WEIGHTS)
                row = {
                    "instance": f"{n} {duration_mode} {window_mode}",
                    "block_status": base["status"],
                    "block_objective": base["objective"],
                    "block_sessions": base["sessions"],
                    "block_seconds": base["elapsed_s"],
                    "candidate_status": cand.status,
                    "candidate_objective": round(cand.objective, 3) if cand.status == "optimal" else None,
                    "candidate_sessions": len(cand.sessions),
                    "candidate_seconds": round(cand.seconds, 3),
                    "declined": len(cand.declined),
                }
                rows.append(row)
                print(
                    f"{row['instance']:<34} {str(row['block_status']):<22} "
                    f"{str(row['block_objective'])[:10]:>10} {str(row['block_sessions']):>8} "
                    f"{row['block_seconds']:>7} {str(row['candidate_objective'])[:10]:>10} "
                    f"{row['candidate_sessions']:>9} {row['candidate_seconds']:>7} {row['declined']:>8}"
                )

    for instance in over_capacity_instances():
        cand = solve(instance["behaviors"], WEIGHTS)
        row = {
            "instance": instance["name"],
            "block_status": "n/a",
            "block_objective": None,
            "block_sessions": None,
            "block_seconds": None,
            "candidate_status": cand.status,
            "candidate_objective": round(cand.objective, 3) if cand.status == "optimal" else None,
            "candidate_sessions": len(cand.sessions),
            "candidate_seconds": round(cand.seconds, 3),
            "declined": len(cand.declined),
            "decline_reasons": sorted({d.reason for d in cand.declined}),
        }
        rows.append(row)
        print(
            f"{row['instance']:<34} {'n/a':<22} {'-':>10} {'-':>8} {'-':>7} "
            f"{str(row['candidate_objective'])[:10]:>10} {row['candidate_sessions']:>9} "
            f"{row['candidate_seconds']:>7} {row['declined']:>8}  {row.get('decline_reasons')}"
        )

    path = os.path.join(HERE, "candidate_bench_results.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
