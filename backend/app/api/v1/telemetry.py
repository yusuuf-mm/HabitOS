"""Telemetry routes — daily aggregation + 7-day trend."""
import logging
from datetime import date, datetime, timezone, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_db, get_current_active_user
from app.models import (
    User,
    OptimizationRun,
    ScheduledBehavior,
    Behavior,
    CompletionLog,
)
from app.models.telemetry import HabitTelemetry
from app.core.constants import MINUTES_PER_PERIOD, PERIODS_PER_DAY
from app.schemas.api import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


async def _aggregate_day(
    db: AsyncSession,
    user_id: UUID,
    target_date: date,
) -> dict:
    """Compute planned/actual metrics for a single day."""

    # 1. Find the active optimization run for the date
    run_result = await db.execute(
        select(OptimizationRun).where(
            (OptimizationRun.user_id == user_id)
            & (OptimizationRun.start_date <= target_date)
            & (OptimizationRun.end_date >= target_date)
            & (OptimizationRun.status == "completed")
        ).order_by(OptimizationRun.created_at.desc())
    )
    run = run_result.scalars().first()
    if not run:
        return {
            "planned_impact": 0.0,
            "actual_impact": 0.0,
            "consistency_score": 0.0,
            "total_behaviors_planned": 0,
            "total_behaviors_completed": 0,
            "total_duration_planned": 0,
            "total_duration_actual": 0,
            "objective_breakdown": {},
            "behavior_breakdown": {},
        }

    day_offset = (target_date - run.start_date).days
    day_start_period = day_offset * PERIODS_PER_DAY
    day_end_period = day_start_period + PERIODS_PER_DAY

    # 2. Fetch scheduled behaviors for this day
    sched_result = await db.execute(
        select(ScheduledBehavior, Behavior)
        .join(Behavior)
        .where(
            (ScheduledBehavior.optimization_run_id == run.id)
            & (ScheduledBehavior.time_period >= day_start_period)
            & (ScheduledBehavior.time_period < day_end_period)
        )
    )
    scheduled_items = sched_result.all()

    planned_count = len(scheduled_items)
    planned_duration = sum(sb.scheduled_duration for sb, _ in scheduled_items)

    # Planned impact = sum of each behavior's weighted impact × scheduled minutes
    planned_impact = 0.0
    objective_breakdown: dict[str, float] = {}
    behavior_breakdown: dict[str, dict] = {}

    for sb, behavior in scheduled_items:
        all_impacts = behavior.get_all_impacts()
        minutes = sb.scheduled_duration
        behavior_impact = 0.0
        for obj_type, impact_val in all_impacts.items():
            behavior_impact += impact_val * minutes
            objective_breakdown[obj_type] = objective_breakdown.get(obj_type, 0.0) + impact_val * minutes
        planned_impact += behavior_impact

        behavior_breakdown[str(behavior.id)] = {
            "name": behavior.name,
            "planned_duration": minutes,
            "planned_impact": round(behavior_impact, 4),
        }

    # 3. Fetch completions for this run
    completion_result = await db.execute(
        select(CompletionLog).where(
            (CompletionLog.user_id == user_id)
            & (CompletionLog.optimization_run_id == run.id)
        )
    )
    completions = completion_result.scalars().all()

    completed_count = len(completions)
    actual_duration = sum(c.actual_duration for c in completions)

    # Actual impact — walk completed behaviors and compute their real impact
    completed_behavior_ids = {c.behavior_id for c in completions}
    actual_impact = 0.0
    for sb, behavior in scheduled_items:
        if behavior.id in completed_behavior_ids:
            all_impacts = behavior.get_all_impacts()
            minutes = sb.scheduled_duration  # use planned duration as the base
            for obj_type, impact_val in all_impacts.items():
                actual_impact += impact_val * minutes
            # Update behavior breakdown
            bid = str(behavior.id)
            if bid in behavior_breakdown:
                behavior_breakdown[bid]["actual_duration"] = sb.scheduled_duration
                behavior_breakdown[bid]["completed"] = True

    # Mark uncompleted behaviors
    for sb, behavior in scheduled_items:
        bid = str(behavior.id)
        if bid in behavior_breakdown and "actual_duration" not in behavior_breakdown[bid]:
            behavior_breakdown[bid]["actual_duration"] = 0
            behavior_breakdown[bid]["completed"] = False

    consistency = (
        (actual_impact / planned_impact * 100) if planned_impact > 0 else 0.0
    )

    return {
        "planned_impact": round(planned_impact, 4),
        "actual_impact": round(actual_impact, 4),
        "consistency_score": round(consistency, 2),
        "total_behaviors_planned": planned_count,
        "total_behaviors_completed": completed_count,
        "total_duration_planned": planned_duration,
        "total_duration_actual": actual_duration,
        "objective_breakdown": objective_breakdown,
        "behavior_breakdown": behavior_breakdown,
    }


@router.post("/daily")
async def aggregate_daily_telemetry(
    target_date: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Aggregate telemetry for a given day (defaults to yesterday)."""
    if target_date:
        snap_date = datetime.strptime(target_date, "%Y-%m-%d").date()
    else:
        snap_date = date.today() - timedelta(days=1)

    metrics = await _aggregate_day(db, current_user.id, snap_date)

    # Upsert — update if exists, create otherwise
    existing_result = await db.execute(
        select(HabitTelemetry).where(
            (HabitTelemetry.user_id == current_user.id)
            & (HabitTelemetry.snapshot_date == snap_date)
        )
    )
    existing = existing_result.scalars().first()

    if existing:
        for k, v in metrics.items():
            setattr(existing, k, v)
        existing.created_at = datetime.now(timezone.utc)
    else:
        telemetry = HabitTelemetry(user_id=current_user.id, snapshot_date=snap_date, **metrics)
        db.add(telemetry)

    await db.commit()

    return ApiResponse(
        success=True,
        message=f"Telemetry aggregated for {snap_date}",
        data=metrics,
    ).dict(exclude_none=True)


@router.get("/trend")
async def get_telemetry_trend(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Return the last N days of telemetry (most recent first)."""
    cutoff = date.today() - timedelta(days=days)
    result = await db.execute(
        select(HabitTelemetry)
        .where(
            (HabitTelemetry.user_id == current_user.id)
            & (HabitTelemetry.snapshot_date >= cutoff)
        )
        .order_by(HabitTelemetry.snapshot_date.desc())
    )
    records = result.scalars().all()

    trend = [
        {
            "date": str(r.snapshot_date),
            "planned_impact": r.planned_impact,
            "actual_impact": r.actual_impact,
            "consistency_score": r.consistency_score,
            "total_behaviors_planned": r.total_behaviors_planned,
            "total_behaviors_completed": r.total_behaviors_completed,
            "total_duration_planned": r.total_duration_planned,
            "total_duration_actual": r.total_duration_actual,
            "objective_breakdown": r.objective_breakdown,
            "behavior_breakdown": r.behavior_breakdown,
        }
        for r in records
    ]

    return ApiResponse(
        data=trend,
        message=f"Retrieved {len(trend)} telemetry records",
    ).dict(exclude_none=True)
