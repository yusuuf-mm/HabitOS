"""Schedule routes."""
import logging
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_db, get_current_active_user
from app.models import User, ScheduledBehavior, OptimizationRun, Behavior, CompletionLog
from app.schemas.api import ApiResponse
from app.schemas.schedule import DailySchedule
from app.schemas.optimization import ScheduledBehaviorResponse, ObjectiveContributionSchema
from app.schemas.tracking import CompletionLogCreate
from app.api.v1.behaviors import map_behavior_to_response, get_objective_map

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.get("", response_model=ApiResponse[DailySchedule])
async def get_daily_schedule(
    date_str: str = Query(None, alias="date"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Get daily schedule."""
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()

    # 1. Find active run covering the date
    result = await db.execute(
        select(OptimizationRun).where(
            (OptimizationRun.user_id == current_user.id) &
            (OptimizationRun.start_date <= target_date) &
            (OptimizationRun.end_date >= target_date) &
            (OptimizationRun.status == "completed")
        ).order_by(OptimizationRun.created_at.desc())
    )
    run = result.scalars().first()

    if not run:
        # Return empty schedule structure if no optimization found
        return ApiResponse(
            data=DailySchedule(
                id=uuid4(), # ephemeral
                user_id=current_user.id,
                date=target_date,
                scheduled_behaviors=[],
                total_duration=0,
                total_energy_spent=0,
                objective_scores=[],
                created_at=datetime.now(timezone.utc),
            ),
            message="No schedule found for this date"
        )

    # 2. Calculate day offset
    day_offset = (target_date - run.start_date).days
    
    scheduled_result = await db.execute(
        select(ScheduledBehavior, Behavior).join(Behavior)
        .where(ScheduledBehavior.optimization_run_id == run.id)
    )
    items = scheduled_result.all()
    
    objective_map = await get_objective_map(db, current_user.id)

    # Mock mapping of time_period integer to "HH:mm".
    def period_to_time(p):
        total_mins = p * 15
        day_mins = total_mins % 1440
        h = day_mins // 60
        m = day_mins % 60
        return f"{h:02d}:{m:02d}"

    periods_per_day = 96
    start_p = day_offset * periods_per_day
    end_p = (day_offset + 1) * periods_per_day
    
    response_items = []
    total_duration = 0
    total_energy = 0
    
    completion_result = await db.execute(
        select(CompletionLog.optimization_run_id, CompletionLog.behavior_id)
        .where(
            (CompletionLog.user_id == current_user.id) &
            (CompletionLog.optimization_run_id == run.id)
        )
    )
    completed_behaviors = { (str(c.optimization_run_id), str(c.behavior_id)) for c in completion_result.all() }

    for sb, behavior in items:
        if sb.time_period >= start_p and sb.time_period < end_p:
            start_time = period_to_time(sb.time_period)
            end_time = period_to_time(sb.time_period + (sb.scheduled_duration // 15))
            
            is_completed = (str(run.id), str(behavior.id)) in completed_behaviors
            
            response_items.append(
                ScheduledBehaviorResponse(
                    id=sb.id,
                    behaviorId=behavior.id,
                    behavior=map_behavior_to_response(behavior, objective_map=objective_map),
                    scheduledDate=target_date,
                    timeSlot="flexible",
                    startTime=start_time,
                    endTime=end_time,
                    duration=sb.scheduled_duration,
                    isCompleted=is_completed,
                )
            )
            total_duration += sb.scheduled_duration
            total_energy += behavior.energy_cost

    # Reconstruct contributions for objective_scores
    contributions = []
    if run.results and "objective_contributions" in run.results:
        for obj_type, data in run.results["objective_contributions"].items():
            obj_id = objective_map.get(obj_type)
            if obj_id:
                contributions.append(
                    ObjectiveContributionSchema(
                        objectiveId=obj_id,
                        objectiveName=obj_type.capitalize(),
                        contribution=data.get("contribution", 0.0),
                        percentage=data.get("percentage", 0.0)
                    )
                )

    return ApiResponse(
        data=DailySchedule(
            id=run.id,
            user_id=current_user.id,
            date=target_date,
            scheduled_behaviors=response_items,
            total_duration=total_duration,
            total_energy_spent=int(total_energy),
            objective_scores=contributions,
            created_at=run.created_at,
        ),
        message="Schedule retrieved successfully"
    )


@router.post("/{scheduled_behavior_id}/complete", response_model=ApiResponse[dict])
async def mark_complete(
    scheduled_behavior_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Mark behavior as complete."""
    result = await db.execute(
        select(ScheduledBehavior).where(
            ScheduledBehavior.id == scheduled_behavior_id
        )
    )
    scheduled = result.scalars().first()
    if not scheduled:
        raise HTTPException(status_code=404, detail="Scheduled behavior not found")

    log_result = await db.execute(
        select(CompletionLog).where(
            (CompletionLog.user_id == current_user.id) &
            (CompletionLog.behavior_id == scheduled.behavior_id) &
            (CompletionLog.optimization_run_id == scheduled.optimization_run_id)
        )
    )
    if log_result.scalars().first():
        return ApiResponse(
            success=True,
            message="Behavior already marked as complete",
            data={}
        )

    completion_log = CompletionLog(
        user_id=current_user.id,
        behavior_id=scheduled.behavior_id,
        optimization_run_id=scheduled.optimization_run_id,
        actual_duration=scheduled.scheduled_duration,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(completion_log)
    await db.commit()

    return ApiResponse(
        success=True,
        message="Behavior marked as complete",
        data={}
    )


@router.post("/{scheduled_behavior_id}/incomplete", response_model=ApiResponse[dict])
async def mark_incomplete(
    scheduled_behavior_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Mark behavior as incomplete."""
    result = await db.execute(
        select(ScheduledBehavior).where(
            ScheduledBehavior.id == scheduled_behavior_id
        )
    )
    scheduled = result.scalars().first()
    if not scheduled:
        raise HTTPException(status_code=404, detail="Scheduled behavior not found")

    log_result = await db.execute(
        select(CompletionLog).where(
            (CompletionLog.user_id == current_user.id) &
            (CompletionLog.behavior_id == scheduled.behavior_id) &
            (CompletionLog.optimization_run_id == scheduled.optimization_run_id)
        )
    )
    log = log_result.scalars().first()
    if log:
        await db.delete(log)
        await db.commit()

    return ApiResponse(
        success=True,
        message="Behavior marked as incomplete",
        data={}
    )
