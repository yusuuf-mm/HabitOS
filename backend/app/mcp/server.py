"""MCP (Model Context Protocol) server for HabitOS.

Exposes tools over stdio for AI-agent integration:
  - ``get_current_schedule``  — fetch today's or a given date's schedule.
  - ``trigger_emergency_reoptimization`` — re-solve the day when a
    behavior is skipped or the schedule is broken.

Run standalone:
    uv run python -m app.mcp.server
"""
import json
import logging
import asyncio
from datetime import date, datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP("habitos", instructions="HabitOS schedule management tools")


@mcp.tool()
async def get_current_schedule(target_date: str | None = None) -> str:
    """Fetch the user's daily schedule.

    Parameters
    ----------
    target_date:
        ISO date string (``YYYY-MM-DD``).  Defaults to today.

    Returns
    -------
    JSON string with scheduled behaviors, durations, and timestamps.
    """
    from app.db.database import async_session_maker as async_session_factory
    from app.api.v1.telemetry import _aggregate_day
    from sqlalchemy import select
    from app.models import OptimizationRun, ScheduledBehavior, Behavior, User

    snap_date = (
        datetime.strptime(target_date, "%Y-%m-%d").date()
        if target_date
        else date.today()
    )

    async with async_session_factory() as db:
        # We don't have a user_id from MCP context — require the caller
        # to provide one or use the most recent run.  For now, grab the
        # most recent run in the database (single-user MCP mode).
        result = await db.execute(
            select(OptimizationRun)
            .where(
                (OptimizationRun.start_date <= snap_date)
                & (OptimizationRun.end_date >= snap_date)
                & (OptimizationRun.status == "completed")
            )
            .order_by(OptimizationRun.created_at.desc())
            .limit(1)
        )
        run = result.scalars().first()
        if not run:
            return json.dumps({"error": "No active schedule found", "date": str(snap_date)})

        day_offset = (snap_date - run.start_date).days
        day_start = day_offset * 96
        day_end = day_start + 96

        sched_result = await db.execute(
            select(ScheduledBehavior, Behavior)
            .join(Behavior)
            .where(
                (ScheduledBehavior.optimization_run_id == run.id)
                & (ScheduledBehavior.time_period >= day_start)
                & (ScheduledBehavior.time_period < day_end)
            )
            .order_by(ScheduledBehavior.time_period)
        )
        items = sched_result.all()

        schedule = []
        for sb, behavior in items:
            from app.core.constants import period_to_time
            start_time = period_to_time(sb.time_period % 96)
            end_time = period_to_time((sb.time_period % 96) + (sb.scheduled_duration // 15))
            schedule.append({
                "behavior": behavior.name,
                "behavior_id": str(behavior.id),
                "scheduled_behavior_id": str(sb.id),
                "start": start_time,
                "end": end_time,
                "duration_minutes": sb.scheduled_duration,
                "time_period": sb.time_period % 96,
            })

        return json.dumps({
            "date": str(snap_date),
            "run_id": str(run.id),
            "total_items": len(schedule),
            "schedule": schedule,
        }, indent=2)


@mcp.tool()
async def trigger_emergency_reoptimization(target_date: str | None = None) -> str:
    """Re-solve the day's schedule after a disruption.

    Fixes all periods up to ``now`` (marking completed behaviors as 1
    and uncompleted as 0) and re-solves the remaining periods.

    Parameters
    ----------
    target_date:
        ISO date string.  Defaults to today.

    Returns
    -------
    JSON string with the new run ID and re-optimized schedule.
    """
    from app.db.database import async_session_maker as async_session_factory
    from app.models import (
        OptimizationRun, ScheduledBehavior, Behavior, CompletionLog,
        Objective, Constraint, User,
    )
    from app.optimization import LinearSolver, OptimizationProblem, BehaviorScheduleInput, ConstraintInput
    from app.core.constants import PERIODS_PER_DAY
    from uuid import uuid4
    from sqlalchemy import select

    snap_date = (
        datetime.strptime(target_date, "%Y-%m-%d").date()
        if target_date
        else date.today()
    )

    async with async_session_factory() as db:
        # Grab the most recent completed run
        result = await db.execute(
            select(OptimizationRun)
            .where(
                (OptimizationRun.start_date <= snap_date)
                & (OptimizationRun.end_date >= snap_date)
                & (OptimizationRun.status == "completed")
            )
            .order_by(OptimizationRun.created_at.desc())
            .limit(1)
        )
        run = result.scalars().first()
        if not run:
            return json.dumps({"error": "No active schedule to re-optimize"})

        # Determine current period within the day
        now = datetime.now(timezone.utc)
        current_minutes = now.hour * 60 + now.minute
        current_period = current_minutes // 15
        day_offset = (snap_date - run.start_date).days
        abs_current = day_offset * PERIODS_PER_DAY + current_period

        # Fetch all scheduled behaviors for this run
        sched_result = await db.execute(
            select(ScheduledBehavior, Behavior)
            .join(Behavior)
            .where(ScheduledBehavior.optimization_run_id == run.id)
        )
        all_items = sched_result.all()

        # Fetch completions
        comp_result = await db.execute(
            select(CompletionLog.behavior_id).where(
                (CompletionLog.user_id == run.user_id)
                & (CompletionLog.optimization_run_id == run.id)
            )
        )
        completed_ids = {row[0] for row in comp_result.all()}

        # Build frozen periods — only the current day's periods up to now
        frozen_periods: dict[int, dict[int, int]] = {}
        behavior_index_map = {}
        behaviors_db = []

        for idx, (sb, behavior) in enumerate(all_items):
            behavior_index_map[behavior.id] = idx
            behaviors_db.append(behavior)
            local_period = sb.time_period % PERIODS_PER_DAY
            blocks = sb.scheduled_duration // 15
            for b in range(blocks):
                t = local_period + b
                if t not in frozen_periods.get(idx, {}):
                    if idx not in frozen_periods:
                        frozen_periods[idx] = {}
                    if t < current_period:
                        # Frozen: 1 if completed, 0 otherwise
                        frozen_periods[idx][t] = 1 if behavior.id in completed_ids else 0

        # Build the optimization problem for the remaining day
        objectives_result = await db.execute(
            select(Objective).where(Objective.user_id == run.user_id)
        )
        objectives_db = objectives_result.scalars().all()
        objectives = {
            obj.type.value if hasattr(obj.type, "value") else str(obj.type): obj.weight
            for obj in objectives_db
        }

        constraints_result = await db.execute(
            select(Constraint).where(
                (Constraint.user_id == run.user_id) & (Constraint.is_active == True)
            )
        )
        constraints_db = constraints_result.scalars().all()
        constraints = [
            ConstraintInput(
                type=c.type.value if hasattr(c.type, "value") else str(c.type),
                parameters=c.parameters,
                is_active=c.is_active,
            )
            for c in constraints_db
        ]

        problem = OptimizationProblem(
            user_id=run.user_id,
            behaviors=[
                BehaviorScheduleInput(
                    id=b.id,
                    name=b.name,
                    min_duration=b.min_duration,
                    typical_duration=b.typical_duration,
                    max_duration=b.max_duration,
                    energy_cost=b.energy_cost,
                    impacts=b.get_all_impacts(),
                    preferred_time_slots=[
                        s.value if hasattr(s, "value") else s
                        for s in b.preferred_time_slots
                    ],
                )
                for b in behaviors_db
            ],
            objectives=objectives,
            constraints=constraints,
            start_date=snap_date,
            end_date=snap_date,
            time_periods=PERIODS_PER_DAY,
        )

        new_run_id = uuid4()
        solver = LinearSolver(timeout_seconds=30)
        solution = solver.solve_partial_day(problem, new_run_id, frozen_periods)

        # Persist the new run
        new_run = OptimizationRun(
            id=new_run_id,
            user_id=run.user_id,
            status="completed" if solution.status == "optimal" else "feasible",
            solver="linear",
            start_date=snap_date,
            end_date=snap_date,
            time_periods=PERIODS_PER_DAY,
            total_objective_value=solution.total_objective_value,
            results=solution.to_dict(),
            diagnostics=solution.diagnostics,
        )
        db.add(new_run)
        for item in solution.schedule_items:
            db.add(ScheduledBehavior(
                optimization_run_id=new_run_id,
                behavior_id=item.behavior_id,
                time_period=item.time_period,
                scheduled_duration=item.scheduled_duration,
                is_scheduled=item.is_scheduled,
            ))
        await db.commit()

        from app.core.constants import period_to_time
        schedule = []
        for item in solution.schedule_items:
            schedule.append({
                "behavior": item.behavior_name,
                "behavior_id": str(item.behavior_id),
                "start": period_to_time(item.time_period % 96),
                "end": period_to_time((item.time_period % 96) + (item.scheduled_duration // 15)),
                "duration_minutes": item.scheduled_duration,
            })

        return json.dumps({
            "new_run_id": str(new_run_id),
            "status": solution.status,
            "total_items": len(schedule),
            "schedule": schedule,
        }, indent=2)


def main():
    """Entry point for ``uv run python -m app.mcp.server``."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
