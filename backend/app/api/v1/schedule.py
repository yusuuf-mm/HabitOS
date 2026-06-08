"""Schedule routes."""
import logging
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.constants import period_to_time, PERIODS_PER_DAY
from app.api.deps import get_db, get_current_active_user
from app.models import User, ScheduledBehavior, OptimizationRun, Behavior, CompletionLog
from app.schemas.api import ApiResponse
from app.schemas.schedule import DailySchedule
from app.schemas.optimization import ScheduledBehaviorResponse, ObjectiveContributionSchema
from app.schemas.tracking import CompletionLogCreate
from app.api.v1.behaviors import map_behavior_to_response, get_objective_map
from app.api.v1.ws import manager

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

    # Items are stored with absolute period indices (0 to PERIODS_PER_DAY - 1).
    day_periods = (target_date - run.start_date).days * PERIODS_PER_DAY

    for sb, behavior in items:
        if day_periods <= sb.time_period < day_periods + PERIODS_PER_DAY:
            start_time = period_to_time(sb.time_period % PERIODS_PER_DAY)
            end_time = period_to_time((sb.time_period % PERIODS_PER_DAY) + (sb.scheduled_duration // 15))
            
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

    # Reconstruct contributions for objective_scores.
    # Percentage is computed from contribution / total objective value.
    contributions = []
    total_value = run.total_objective_value or 0.0
    if run.results and "objective_contributions" in run.results:
        for obj_type, data in run.results["objective_contributions"].items():
            obj_id = objective_map.get(obj_type)
            if obj_id:
                contrib = data.get("contribution", 0.0)
                pct = (contrib / total_value * 100) if total_value > 0 else 0.0
                contributions.append(
                    ObjectiveContributionSchema(
                        objectiveId=obj_id,
                        objectiveName=obj_type.capitalize(),
                        contribution=contrib,
                        percentage=round(pct, 2),
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

    await manager.broadcast_schedule_update(current_user.id)

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

    await manager.broadcast_schedule_update(current_user.id)

    return ApiResponse(
        success=True,
        message="Behavior marked as incomplete",
        data={}
    )


@router.post("/reoptimize", response_model=ApiResponse[dict])
async def partial_reoptimize(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Re-optimize the remaining periods of the current day.

    Freezes all periods before *now* and re-solves the future.  Returns
    the new optimization run ID and updated schedule.
    """
    from datetime import timedelta
    from uuid import uuid4 as _uuid4
    from sqlalchemy import select as sa_select
    from app.models import Objective, Constraint
    from app.optimization import LinearSolver, OptimizationProblem, BehaviorScheduleInput, ConstraintInput

    target_date = date.today()

    # 1. Find active run
    run_result = await db.execute(
        sa_select(OptimizationRun).where(
            (OptimizationRun.user_id == current_user.id)
            & (OptimizationRun.start_date <= target_date)
            & (OptimizationRun.end_date >= target_date)
            & (OptimizationRun.status == "completed")
        ).order_by(OptimizationRun.created_at.desc())
    )
    run = run_result.scalars().first()
    if not run:
        raise HTTPException(status_code=404, detail="No active schedule to re-optimize")

    # 2. Determine current period
    now = datetime.now(timezone.utc)
    current_minutes = now.hour * 60 + now.minute
    current_period = current_minutes // 15
    day_offset = (target_date - run.start_date).days

    # 3. Fetch all scheduled behaviors + completions
    sched_result = await db.execute(
        sa_select(ScheduledBehavior, Behavior)
        .join(Behavior)
        .where(ScheduledBehavior.optimization_run_id == run.id)
    )
    all_items = sched_result.all()

    comp_result = await db.execute(
        sa_select(CompletionLog.behavior_id).where(
            (CompletionLog.user_id == current_user.id)
            & (CompletionLog.optimization_run_id == run.id)
        )
    )
    completed_ids = {row[0] for row in comp_result.all()}

    # 4. Build frozen periods
    frozen_periods: dict[int, dict[int, int]] = {}
    behaviors_db = []
    behavior_index_map: dict[UUID, int] = {}

    for idx, (sb, behavior) in enumerate(all_items):
        behavior_index_map[behavior.id] = idx
        behaviors_db.append(behavior)
        local_period = sb.time_period % PERIODS_PER_DAY
        blocks = sb.scheduled_duration // 15
        for b in range(blocks):
            t = local_period + b
            if idx not in frozen_periods:
                frozen_periods[idx] = {}
            if t < current_period:
                frozen_periods[idx][t] = 1 if behavior.id in completed_ids else 0

    # 5. Build problem
    obj_result = await db.execute(
        sa_select(Objective).where(Objective.user_id == current_user.id)
    )
    objectives_db = obj_result.scalars().all()
    objectives = {
        o.type.value if hasattr(o.type, "value") else str(o.type): o.weight
        for o in objectives_db
    }

    con_result = await db.execute(
        sa_select(Constraint).where(
            (Constraint.user_id == current_user.id) & (Constraint.is_active == True)
        )
    )
    constraints_db = con_result.scalars().all()
    constraints = [
        ConstraintInput(
            type=c.type.value if hasattr(c.type, "value") else str(c.type),
            parameters=c.parameters,
            is_active=c.is_active,
        )
        for c in constraints_db
    ]

    problem = OptimizationProblem(
        user_id=current_user.id,
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
        start_date=target_date,
        end_date=target_date,
        time_periods=PERIODS_PER_DAY,
    )

    # 6. Solve
    new_run_id = _uuid4()
    solver = LinearSolver(timeout_seconds=30)
    solution = solver.solve_partial_day(problem, new_run_id, frozen_periods)

    # 7. Persist
    new_run = OptimizationRun(
        id=new_run_id,
        user_id=current_user.id,
        status="completed" if solution.status == "optimal" else "feasible",
        solver="linear",
        start_date=target_date,
        end_date=target_date,
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

    # 8. Broadcast + return
    await manager.broadcast_reoptimization(current_user.id, str(new_run_id))

    schedule = []
    for item in solution.schedule_items:
        schedule.append({
            "behavior": item.behavior_name,
            "behavior_id": str(item.behavior_id),
            "start": period_to_time(item.time_period % PERIODS_PER_DAY),
            "end": period_to_time((item.time_period % PERIODS_PER_DAY) + (item.scheduled_duration // 15)),
            "duration_minutes": item.scheduled_duration,
        })

    return ApiResponse(
        data={
            "new_run_id": str(new_run_id),
            "status": solution.status,
            "schedule": schedule,
        },
        message="Partial re-optimization completed",
    )
