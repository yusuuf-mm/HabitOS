"""Prototype vs brute-force oracle on tiny random instances.

Twelve periods, three behaviours, four categories (feasible, over-capacity,
protected conflict, impossible minimum). Prints the match count and every
disagreement, so the Phase 3 review has the raw evidence.

    uv run python tools/oracle_compare.py
"""
from __future__ import annotations

import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from candidate_model import Behavior, PERIODS_PER_DAY, solve  # noqa: E402
from oracle import solve_bruteforce  # noqa: E402

PERIODS = 12
WEIGHTS = {"health": 0.6, "productivity": 0.4}


def _behavior(rng, index: int, *, lo: int, hi: int, window: tuple[int, int],
              protected: bool = False) -> Behavior:
    return Behavior(
        id=f"b{index}",
        name=f"Behaviour {index}",
        min_duration=lo,
        max_duration=hi,
        impacts={
            "health": round(rng.uniform(0.1, 1.0), 2),
            "productivity": round(rng.uniform(0.1, 1.0), 2),
        },
        windows=[window],
        protected=protected,
    )


def build_case(rng, category: str) -> list[Behavior]:
    if category == "feasible":
        behaviors = []
        for index in range(3):
            lo = rng.choice([15, 30])
            hi = lo + rng.choice([0, 15])
            start = rng.randint(0, 3)
            behaviors.append(
                _behavior(rng, index, lo=lo, hi=hi, window=(start, start + rng.randint(3, 8)))
            )
        return behaviors
    if category == "over_capacity":
        return [
            _behavior(rng, index, lo=45, hi=45, window=(0, 5), protected=False)
            for index in range(3)
        ]
    if category == "protected_conflict":
        return [
            _behavior(rng, 0, lo=15, hi=15, window=(0, 2), protected=True),
            _behavior(rng, 1, lo=15, hi=15, window=(0, 2), protected=True),
            _behavior(rng, 2, lo=15, hi=30, window=(0, 2), protected=False),
        ]
    if category == "impossible_minimum":
        return [
            _behavior(rng, index, lo=240, hi=300, window=(0, PERIODS), protected=False)
            for index in range(3)
        ]
    raise ValueError(category)


def main() -> None:
    rng = random.Random(20261114)
    categories = ["feasible", "over_capacity", "protected_conflict", "impossible_minimum"]
    rows = []
    matches = 0
    schedule_matches = 0
    total = 0

    for category in categories:
        for _ in range(10):
            behaviors = build_case(rng, category)
            prototype = solve(behaviors, WEIGHTS, periods=PERIODS)
            oracle = solve_bruteforce(behaviors, WEIGHTS, periods=PERIODS)
            total += 1

            objective_match = (
                prototype.status == oracle.status
                and abs((prototype.objective or 0.0) - (oracle.objective or 0.0)) <= 1e-6
            )
            prototype_schedule = sorted((s.behavior_id, s.start, s.duration) for s in prototype.sessions)
            oracle_schedule = sorted((s.behavior_id, s.start, s.duration) for s in oracle.sessions)
            schedule_match = prototype_schedule == oracle_schedule
            if objective_match:
                matches += 1
            if schedule_match:
                schedule_matches += 1

            row = {
                "category": category,
                "behaviors": len(behaviors),
                "prototype_objective": round(prototype.objective, 6)
                if prototype.status == "Optimal"
                else None,
                "oracle_objective": round(oracle.objective, 6) if oracle.status == "Optimal" else None,
                "prototype_declined": [d.behavior_id for d in prototype.declined],
                "oracle_declined": [d.behavior_id for d in oracle.declined],
                "objective_match": objective_match,
                "schedule_match": schedule_match,
            }
            rows.append(row)
            if not objective_match:
                print("DISAGREEMENT", json.dumps(row))

    print(f"\nobjective matches: {matches}/{total}")
    print(f"identical schedules: {schedule_matches}/{total}")
    for category in categories:
        subset = [r for r in rows if r["category"] == category]
        print(
            f"  {category:<20} {sum(1 for r in subset if r['objective_match'])}/{len(subset)} "
            f"(identical schedules {sum(1 for r in subset if r['schedule_match'])}/{len(subset)})"
        )

    path = os.path.join(HERE, "oracle_results.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
