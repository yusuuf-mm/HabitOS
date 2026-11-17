"""Generate the landing page's hero day with the real planner.

The landing grid used to be 96 random squares. This script solves a small demo
day with the shipped solver and writes the result to
``frontend/src/data/heroDay.json``; the page renders that, so what it shows is a
plan the engine actually produced (regenerate with ``npm run gen:hero``).

The demo day is fixed on purpose: same habits, same weights, same plan, so the
page cannot drift without a visible diff.
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.optimization import CandidateSolver  # noqa: E402
from app.optimization.models import BehaviorScheduleInput, OptimizationProblem  # noqa: E402

PERIODS = 96
OUT = ROOT / "frontend" / "src" / "data" / "heroDay.json"

DEMO = [
    # name, min, max, slots, impacts
    ("Morning walk", 30, 45, ["early_morning"], {"health": 0.9, "mindfulness": 0.4}),
    ("Deep work", 90, 120, ["morning"], {"productivity": 1.0, "learning": 0.3}),
    ("Lunch", 30, 45, ["midday"], {"health": 0.5, "social": 0.4}),
    ("Study", 45, 60, ["afternoon"], {"learning": 1.0}),
    ("Strength", 45, 60, ["evening"], {"health": 1.0}),
    ("Read", 30, 30, ["night"], {"learning": 0.5, "mindfulness": 0.6}),
]


def build_problem() -> OptimizationProblem:
    behaviours = [
        BehaviorScheduleInput(
            id=UUID(int=index + 1),
            name=name,
            min_duration=lo,
            typical_duration=lo,
            max_duration=hi,
            energy_cost=1.0,
            impacts=impacts,
            preferred_time_slots=slots,
            protected=False,
        )
        for index, (name, lo, hi, slots, impacts) in enumerate(DEMO)
    ]
    weights = {"health": 0.3, "productivity": 0.25, "learning": 0.2, "mindfulness": 0.15, "social": 0.1}
    return OptimizationProblem(
        user_id=UUID(int=999),
        behaviors=behaviours,
        objectives=weights,
        constraints=[],
        start_date=date(2026, 6, 8),
        end_date=date(2026, 6, 8),
        time_periods=PERIODS,
    )


def main() -> None:
    problem = build_problem()
    solution = CandidateSolver(timeout_seconds=10).solve(problem, UUID(int=1000))
    if solution.status != "optimal":
        raise SystemExit(f"hero day did not solve: {solution.status}")

    cells = []
    for period in range(PERIODS):
        label = None
        for item in solution.schedule_items:
            start = item.time_period
            end = start + item.scheduled_duration // 15
            if start <= period < end:
                label = item.behavior_name
                break
        if label is not None:
            kind = "session"
        elif period < 20:
            kind = "night"
        else:
            kind = "free"
        cells.append({"period": period, "kind": kind, "label": label})

    payload = {
        "generatedBy": "tools/generate_hero_day.py",
        "solver": solution.solver,
        "value": solution.total_objective_value,
        "sessions": [
            {
                "name": item.behavior_name,
                "startPeriod": item.time_period,
                "start": f"{(item.time_period * 15) // 60:02d}:{(item.time_period * 15) % 60:02d}",
                "minutes": item.scheduled_duration,
            }
            for item in solution.schedule_items
        ],
        "cells": cells,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(solution.schedule_items)} sessions, value {solution.total_objective_value})")


if __name__ == "__main__":
    main()
