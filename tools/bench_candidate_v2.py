"""Measured comparison: candidate-placement prototype vs the block model.

Covers the original 12 instances, three over-capacity instances, and 20- and
25-behaviour cases at the documented cap (25 active behaviours). Instances above
the cap must be refused, never truncated.

Pass criteria (Phase 3 gate):
  * every instance with <= 20 behaviours proves optimality in under 3 s;
  * 21-25 behaviours either prove optimality within the time limit, or are
    reported with their times;
  * no non-optimal result is presented as a plan.

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
from candidate_model import (  # noqa: E402
    Behavior,
    MAX_BEHAVIORS,
    PERIODS_PER_DAY,
    PlanTooLargeError,
    solve,
)

from app.core.constants import periods_for_time_slots  # noqa: E402

WEIGHTS = {"health": 0.6, "productivity": 0.4}
TIME_LIMIT = 30


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
    morning = periods_for_time_slots(["morning"])
    narrow = [(min(morning), max(morning) + 1)]
    wide = [(20, 96)]
    return [
        {
            "name": "15x60min in 300min",
            "behaviors": [
                Behavior(id=f"a{i}", name=f"Protected {i}", min_duration=60, max_duration=60,
                         impacts={"health": 1.0}, windows=narrow, protected=True)
                for i in range(15)
            ],
        },
        {
            "name": "40x45min in 1140min",
            "behaviors": [
                Behavior(id=f"b{i}", name=f"Flexible {i}", min_duration=45, max_duration=90,
                         impacts={"health": 0.5, "productivity": 0.5}, windows=wide)
                for i in range(40)
            ],
        },
        {
            "name": "12 protected x45min in 300min",
            "behaviors": [
                Behavior(id=f"c{i}", name=f"Must-do {i}", min_duration=45, max_duration=45,
                         impacts={"health": 1.0}, windows=narrow, protected=True)
                for i in range(12)
            ],
        },
    ]


def run_candidate(behaviors, time_limit=TIME_LIMIT) -> dict:
    try:
        result = solve(behaviors, WEIGHTS, time_limit=time_limit)
    except PlanTooLargeError as exc:
        return {"status": "refused", "objective": None, "sessions": None,
                "seconds": None, "declined": None, "note": str(exc)}
    return {
        "status": result.status,
        "objective": round(result.objective, 3) if result.status == "optimal" else None,
        "sessions": len(result.sessions),
        "seconds": round(result.seconds, 3),
        "declined": len(result.declined),
        "note": "",
    }


def main() -> None:
    rows: list[dict] = []
    failures: list[str] = []

    print(f"{'instance':<28} {'block':<20} {'blk obj':>9} {'blk s':>6} "
          f"{'cand':<10} {'cand obj':>9} {'sess':>5} {'cand s':>7} {'decl':>5}")
    print("-" * 105)

    def record(name: str, n: int, base=None, cand=None, behaviors=None):
        if cand is None:
            cand = run_candidate(behaviors)
        row = {
            "instance": name,
            "behaviours": n,
            "block_status": base["status"] if base else "n/a",
            "block_objective": base["objective"] if base else None,
            "block_seconds": base["elapsed_s"] if base else None,
            "candidate_status": cand["status"],
            "candidate_objective": cand["objective"],
            "candidate_sessions": cand["sessions"],
            "candidate_seconds": cand["seconds"],
            "declined": cand["declined"],
            "note": cand["note"],
        }
        rows.append(row)
        print(f"{name:<28} {row['block_status']:<20} {str(row['block_objective']):>9} "
              f"{str(row['block_seconds']):>6} {cand['status']:<10} "
              f"{str(cand['objective']):>9} {str(cand['sessions']):>5} "
              f"{str(cand['seconds']):>7} {str(cand['declined']):>5}")

        # Gate criteria.
        if n <= 20:
            if cand["status"] != "optimal":
                failures.append(f"{name}: {cand['status']} (must be optimal)")
            elif cand["seconds"] is not None and cand["seconds"] >= 3.0:
                failures.append(f"{name}: {cand['seconds']}s (>= 3s)")
        elif n <= MAX_BEHAVIORS:
            if cand["status"] not in {"optimal"} and not cand["note"]:
                failures.append(f"{name}: {cand['status']} without a timeout note")
        else:
            if cand["status"] != "refused":
                failures.append(f"{name}: {n} > {MAX_BEHAVIORS} was not refused")

    for n in (10, 20):
        for duration_mode in ("fixed", "variable"):
            for window_mode in ("narrow", "wide"):
                name = f"{n} {duration_mode} {window_mode}"
                base = bench_cbc.run_case(n, duration_mode, window_mode)
                problem = bench_cbc.build_problem(n, duration_mode, window_mode)
                record(name, n, base=base, behaviors=to_prototype(problem))

    # Over-cap (40) instances must be refused, not silently truncated.
    for duration_mode in ("fixed", "variable"):
        for window_mode in ("narrow", "wide"):
            name = f"40 {duration_mode} {window_mode}"
            base = bench_cbc.run_case(40, duration_mode, window_mode)
            problem = bench_cbc.build_problem(40, duration_mode, window_mode)
            record(name, 40, base=base, behaviors=to_prototype(problem))

    # 25-behaviour cases at the cap.
    for duration_mode in ("fixed", "variable"):
        name = f"25 {duration_mode} wide"
        problem = bench_cbc.build_problem(25, duration_mode, "wide")
        record(name, 25, behaviors=to_prototype(problem))

    for instance in over_capacity_instances():
        record(instance["name"], len(instance["behaviors"]), behaviors=instance["behaviors"])

    print("\nGate criteria:")
    if failures:
        print("  FAIL")
        for failure in failures:
            print(f"    - {failure}")
    else:
        print("  PASS — every <=20 instance optimal under 3s; 21-25 reported; nothing truncated")

    path = os.path.join(HERE, "candidate_bench_results.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"rows": rows, "failures": failures}, handle, indent=2)
    print(f"wrote {path}")

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
