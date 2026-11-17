"""Why did behaviours get declined? Reason codes plus a free-capacity audit.

A decline is only acceptable when either (a) the behaviour's net value is
negative, or (b) no candidate fits in the free periods (window/capacity conflict).
Anything else is reported as a bug.

    uv run python tools/decline_analysis.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "backend")))

import bench_cbc  # noqa: E402
from bench_candidate_v2 import over_capacity_instances, to_prototype  # noqa: E402
from candidate_model import PlanTooLargeError, generate_candidates, solve  # noqa: E402

WEIGHTS = {"health": 0.6, "productivity": 0.4}


def audit(name, behaviors, periods=96, frozen=None):
    try:
        result = solve(behaviors, WEIGHTS, periods=periods, frozen=frozen)
    except PlanTooLargeError as exc:
        print()
        print(f"{name}: refused - {exc}")
        return 0
    occupied = set()
    for session in result.sessions:
        occupied.update(range(session.start, session.start + session.duration // 15))
    free = set(range(periods)) - occupied - set(frozen or {})

    print(f"\n{name}: {len(result.sessions)} sessions, {len(result.declined)} declined")
    for session in sorted(result.sessions, key=lambda s: s.start):
        print(f"  scheduled  {session.behavior_name:<22} start={session.start:>2} "
              f"dur={session.duration:>3}")
    bugs = 0
    for decline in result.declined:
        behavior = next(b for b in behaviors if b.id == decline.behavior_id)
        candidates = [
            (start, length)
            for start, length in generate_candidates(behavior, periods)
            if all(period in free for period in range(start, start + length))
        ]
        score = behavior.score(WEIGHTS)
        value = "n/a" if candidates else "no fitting candidate"
        if candidates and score > 0:
            bugs += 1
            value = f"BUG: fits at {candidates[:3]} with positive score {score}"
        print(f"  declined   {decline.behavior_name:<22} reason={decline.reason:<24} {value}")
    print(f"  declines with free capacity and positive value: {bugs}")
    return bugs


def main() -> None:
    bugs = 0
    for window_mode in ("narrow", "wide"):
        problem = bench_cbc.build_problem(10, "variable", window_mode)
        bugs += audit(f"10 variable {window_mode}", to_prototype(problem))

    for instance in over_capacity_instances():
        bugs += audit(instance["name"], instance["behaviors"])

    print(f"\ntotal declines that need explaining beyond free-capacity/value: {bugs}")


if __name__ == "__main__":
    main()
