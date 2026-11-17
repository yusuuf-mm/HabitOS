"""Prototype vs brute-force oracle, 1,000 tiny instances.

Four behaviours, 12-16 periods, five categories: feasible, multi-session with a
minimum gap, frozen periods, protected conflict, over-capacity. Both schedules
must have the same objective and must pass `validate_plan`. A 100-instance
canonical set also checks the production `validate_schedule`, which only
understands named time slots and therefore cannot express a 12-16 period window.

    uv run python tools/oracle_compare.py
"""
from __future__ import annotations

import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "backend")))

from candidate_model import (  # noqa: E402
    Behavior,
    MAX_BEHAVIORS,
    PlanTooLargeError,
    solve,
    validate_plan,
)
from oracle import solve_bruteforce  # noqa: E402

WEIGHTS = {"health": 0.6, "productivity": 0.4}
PER_CATEGORY = 200
CATEGORIES = [
    "feasible",
    "multi_session_gap",
    "frozen",
    "protected_conflict",
    "over_capacity",
]


def _behavior(rng, index, *, lo, hi, window, protected=False, sessions=1, gap=0):
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
        sessions=sessions,
        min_gap=gap,
    )


def build_case(rng, category, periods):
    if category == "feasible":
        return [
            _behavior(
                rng, i, lo=15, hi=30,
                window=(start := rng.randint(0, 2), start + rng.randint(3, 5)),
            )
            for i in range(4)
        ], {}
    if category == "multi_session_gap":
        return [
            _behavior(rng, i, lo=15, hi=15, window=(0, min(periods, 4)), sessions=2, gap=15)
            for i in range(4)
        ], {}
    if category == "frozen":
        frozen = {period: 1 for period in rng.sample(range(periods), k=2)}
        return [
            _behavior(
                rng, i, lo=15, hi=15,
                window=(start := rng.randint(0, 2), start + rng.randint(4, 6)),
            )
            for i in range(4)
        ], frozen
    if category == "protected_conflict":
        return [
            _behavior(rng, 0, lo=15, hi=15, window=(0, 2), protected=True),
            _behavior(rng, 1, lo=15, hi=15, window=(0, 2), protected=True),
            _behavior(rng, 2, lo=15, hi=30, window=(0, periods)),
            _behavior(rng, 3, lo=15, hi=30, window=(0, periods)),
        ], {}
    if category == "over_capacity":
        return [
            _behavior(rng, i, lo=60, hi=60, window=(0, 5))
            for i in range(4)
        ], {}
    raise ValueError(category)


def main() -> None:
    rng = random.Random(20261114)
    rows = []
    totals = {category: {"total": 0, "match": 0, "violations": 0} for category in CATEGORIES}
    disagreements = []

    for category in CATEGORIES:
        for _ in range(PER_CATEGORY):
            periods = rng.randint(12, 16)
            behaviors, frozen = build_case(rng, category, periods)
            try:
                prototype = solve(behaviors, WEIGHTS, periods=periods, frozen=frozen)
            except PlanTooLargeError as exc:  # cannot happen at 4 behaviours
                raise SystemExit(str(exc))
            oracle = solve_bruteforce(behaviors, WEIGHTS, periods=periods, frozen=frozen)

            prototype_ok = prototype.status == "optimal"
            oracle_ok = oracle.status == "optimal"
            same_status = prototype_ok == oracle_ok
            objective_match = same_status and (
                not prototype_ok
                or abs(prototype.objective - oracle.objective) <= 1e-6
            )
            prototype_violations = (
                validate_plan(behaviors, prototype, periods=periods, frozen=frozen)
                if prototype_ok
                else []
            )
            oracle_violations = (
                validate_plan(behaviors, oracle, periods=periods, frozen=frozen)
                if oracle_ok
                else []
            )

            totals[category]["total"] += 1
            if objective_match:
                totals[category]["match"] += 1
            if prototype_violations or oracle_violations:
                totals[category]["violations"] += 1
            if not objective_match or prototype_violations or oracle_violations:
                disagreements.append(
                    {
                        "category": category,
                        "periods": periods,
                        "prototype_status": prototype.status,
                        "prototype_objective": None if not prototype_ok else round(prototype.objective, 6),
                        "oracle_status": oracle.status,
                        "oracle_objective": None if not oracle_ok else round(oracle.objective, 6),
                        "prototype_violations": prototype_violations,
                        "oracle_violations": oracle_violations,
                    }
                )

    total = sum(category["total"] for category in totals.values())
    matched = sum(category["match"] for category in totals.values())
    violations = sum(category["violations"] for category in totals.values())

    print(f"objective matches: {matched}/{total}")
    print(f"instances with validation violations: {violations}")
    for category in CATEGORIES:
        print(f"  {category:<20} {totals[category]['match']}/{totals[category]['total']} "
              f"(violations {totals[category]['violations']})")
    if disagreements:
        print("\nDISAGREEMENTS")
        for entry in disagreements[:10]:
            print(" ", json.dumps(entry))

    # Production validator, on instances whose windows are canonical slots.
    from app.optimization.models import BehaviorScheduleInput, OptimizationProblem, ScheduleItem
    from app.optimization.status import validate_schedule
    from app.core.constants import periods_for_time_slots
    from datetime import date
    from uuid import uuid4

    canonical_failures = 0
    for _ in range(100):
        behaviors = [
            _behavior(rng, i, lo=15, hi=30, window=(20, 96)) for i in range(4)
        ]
        result = solve(behaviors, WEIGHTS, periods=96)
        id_map = {behavior.id: uuid4() for behavior in behaviors}
        problem = OptimizationProblem(
            user_id=uuid4(),
            behaviors=[
                BehaviorScheduleInput(
                    id=id_map[behavior.id],
                    name=behavior.name,
                    min_duration=behavior.min_duration,
                    typical_duration=behavior.min_duration,
                    max_duration=behavior.max_duration,
                    energy_cost=1.0,
                    impacts=behavior.impacts,
                    preferred_time_slots=["flexible"],
                )
                for behavior in behaviors
            ],
            objectives=WEIGHTS,
            constraints=[],
            start_date=date.today(),
            end_date=date.today(),
            time_periods=96,
        )
        items = [
            ScheduleItem(
                behavior_id=id_map[session.behavior_id],
                behavior_name=session.behavior_name,
                time_period=session.start,
                scheduled_duration=session.duration,
                is_scheduled=True,
            )
            for session in result.sessions
        ]
        if validate_schedule(problem, items):
            canonical_failures += 1

    print(f"production validate_schedule: {100 - canonical_failures}/100 clean")

    path = os.path.join(HERE, "oracle_results.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "totals": totals,
                "disagreements": disagreements,
                "validate_schedule_clean": 100 - canonical_failures,
            },
            handle,
            indent=2,
        )
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
