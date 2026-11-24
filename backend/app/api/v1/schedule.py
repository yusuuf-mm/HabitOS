"""Schedule routes."""
import logging
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core import clock
from app.core.constants import period_to_time, PERIODS_PER_DAY
from app.services.metrics import (
    day_runs,
    local_today,
    resolve_day_plan,
    session_start,
    user_zone,
)
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
    today = local_today(user_zone(current_user))
    target_date = (
        datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else today
    )

    # 1. Find the schedule-visible run covering the date. Week plans write a
    # visible run even when the solver only reached a feasible solution.
    result = await db.execute(
        select(OptimizationRun).where(
            (OptimizationRun.user_id == current_user.id) &
            (OptimizationRun.start_date <= target_date) &
            (OptimizationRun.end_date >= target_date) &
            (OptimizationRun.status == "completed")
        ).order_by(OptimizationRun.created_at.desc())
    )
    run = result.scalars().first()

    committed = (
        run is not None
        and run.baseline_revision is not None
        and run.plan_revision == run.baseline_revision
    )
    plan_source = (
        "draft" if target_date > today else "committed" if committed else "fallback"
    )

    if not run:
        # Return empty schedule structure if no optimization found
        plan_source = "none"
        return ApiResponse(
            data=DailySchedule(
                id=uuid4(), # ephemeral
                user_id=current_user.id,
                date=target_date,
                scheduled_behaviors=[],
                total_duration=0,
                objective_scores=[],
                created_at=clock.now_utc(),
                declines=[],
                planSource=plan_source,
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
    
    # Completion belongs to one planned session, not to the behaviour: the same
    # behaviour can be scheduled twice in a day and only one of those sessions
    # may be done (docs/METRIC.md §4).
    completion_result = await db.execute(
        select(CompletionLog.planned_session_id)
        .where(
            (CompletionLog.user_id == current_user.id) &
            (CompletionLog.optimization_run_id == run.id)
        )
    )
    completed_sessions = {
        row[0] for row in completion_result.all() if row[0] is not None
    }

    # Items are stored with absolute period indices (0 to PERIODS_PER_DAY - 1).
    day_periods = (target_date - run.start_date).days * PERIODS_PER_DAY

    for sb, behavior in items:
        if day_periods <= sb.time_period < day_periods + PERIODS_PER_DAY:
            start_time = period_to_time(sb.time_period % PERIODS_PER_DAY)
            end_time = period_to_time((sb.time_period % PERIODS_PER_DAY) + (sb.scheduled_duration // 15))
            
            is_completed = sb.planned_session_id in completed_sessions

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
                    plannedSessionId=sb.planned_session_id,
                    isCompleted=is_completed,
                    releasedAt=sb.released_at,
                )
            )
            total_duration += sb.scheduled_duration

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
            objective_scores=contributions,
            created_at=run.created_at,
            declines=list((run.diagnostics or {}).get("declines", [])),
            planSource=plan_source,
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
        select(ScheduledBehavior)
        .join(OptimizationRun)
        .where(
            (ScheduledBehavior.id == scheduled_behavior_id)
            & (OptimizationRun.user_id == current_user.id)
        )
    )
    scheduled = result.scalars().first()
    if not scheduled:
        raise HTTPException(status_code=404, detail="Scheduled behavior not found")

    log_result = await db.execute(
        select(CompletionLog).where(
            (CompletionLog.user_id == current_user.id) &
            (CompletionLog.planned_session_id == scheduled.planned_session_id) &
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
        planned_session_id=scheduled.planned_session_id,
        actual_duration=scheduled.scheduled_duration,
        completed_at=clock.now_utc(),
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
        select(ScheduledBehavior)
        .join(OptimizationRun)
        .where(
            (ScheduledBehavior.id == scheduled_behavior_id)
            & (OptimizationRun.user_id == current_user.id)
        )
    )
    scheduled = result.scalars().first()
    if not scheduled:
        raise HTTPException(status_code=404, detail="Scheduled behavior not found")

    log_result = await db.execute(
        select(CompletionLog).where(
            (CompletionLog.user_id == current_user.id) &
            (CompletionLog.planned_session_id == scheduled.planned_session_id) &
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


@router.post("/{scheduled_behavior_id}/release", response_model=ApiResponse[dict])
async def release_session(
    scheduled_behavior_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Withdraw a session before it starts (docs/METRIC.md §3.2).

    A released session leaves the completion-rate denominator and is reported
    beside the rate. After the session has started it can only be missed.
    """
    result = await db.execute(
        select(ScheduledBehavior)
        .join(OptimizationRun)
        .where(
            (ScheduledBehavior.id == scheduled_behavior_id)
            & (OptimizationRun.user_id == current_user.id)
        )
    )
    scheduled = result.scalars().first()
    if not scheduled:
        raise HTTPException(status_code=404, detail="Scheduled behavior not found")

    run = await db.get(OptimizationRun, scheduled.optimization_run_id)
    if scheduled.released_at is not None:
        return ApiResponse(
            success=True,
            message="Session already released",
            data={"released_at": scheduled.released_at.isoformat()},
        )

    tz = user_zone(current_user)
    now = clock.now_utc()
    if now >= session_start(run.start_date, scheduled.time_period, tz):
        raise HTTPException(
            status_code=409,
            detail="This session has already started; it counts as missed, not released.",
        )

    completed = await db.execute(
        select(CompletionLog).where(
            (CompletionLog.user_id == current_user.id)
            & (CompletionLog.planned_session_id == scheduled.planned_session_id)
            & (CompletionLog.optimization_run_id == scheduled.optimization_run_id)
        )
    )
    if completed.scalars().first():
        raise HTTPException(
            status_code=409, detail="This session is already completed"
        )

    scheduled.released_at = now
    await db.commit()
    await manager.broadcast_schedule_update(current_user.id)

    return ApiResponse(
        success=True,
        message="Session released",
        data={"released_at": now.isoformat()},
    )


@router.post("/commit", response_model=ApiResponse[dict])
async def commit_baseline(
    run_id: UUID = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Accept a plan as today's baseline (docs/METRIC.md §2).

    Exactly one run per day can be the baseline. While the baseline is open it may
    be re-committed; once it freezes this returns 409.
    """
    tz = user_zone(current_user)
    today = local_today(tz)
    runs = await day_runs(db, current_user.id, today)
    if not runs:
        raise HTTPException(status_code=404, detail="No plan to commit for today")

    plan = await resolve_day_plan(db, current_user, today)
    if plan.source == "committed":
        return ApiResponse(
            success=True,
            message="Baseline already committed",
            data={
                "run_id": str(plan.run.id),
                "baseline_revision": plan.run.baseline_revision,
                "committed_at": plan.run.committed_at.isoformat()
                if plan.run.committed_at
                else None,
            },
        )
    if plan.frozen:
        raise HTTPException(
            status_code=409,
            detail=(
                "The baseline is frozen (the first session started or the day "
                "began); it can no longer be committed or changed."
            ),
        )

    target = next((run for run in runs if run.id == run_id), None) if run_id else runs[-1]
    if target is None:
        raise HTTPException(status_code=404, detail="Plan not found for today")

    now = clock.now_utc()
    for other in runs:  # one baseline per day
        other.baseline_revision = None
    target.baseline_revision = target.plan_revision or 1
    target.committed_at = now
    await db.commit()

    return ApiResponse(
        success=True,
        message="Baseline committed",
        data={
            "run_id": str(target.id),
            "baseline_revision": target.baseline_revision,
            "committed_at": now.isoformat(),
        },
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
    from app.core.exceptions import SolverBusyError
    from app.optimization import (
        BehaviorScheduleInput,
        CandidateSolver,
        ConstraintInput,
        OptimizationProblem,
        normalise_weights,
        record_weights,
        run_in_solver_pool,
    )

    # "Today" is the plan-local day, the same clock the metric uses: the server's
    # date can already be tomorrow while the user's day is still running.
    tz = user_zone(current_user)
    target_date = local_today(tz)

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

    # 2. Determine the current period in the user's plan-local clock, not the
    # server's UTC clock (docs/METRIC.md §5), and honour the target date: a past
    # day is entirely elapsed, a future day is entirely ahead.
    now_local = clock.now_utc().astimezone(tz)
    current_period = (now_local.hour * 60 + now_local.minute) // 15
    day_offset = (target_date - local_today(tz)).days
    if day_offset < 0:
        current_period = PERIODS_PER_DAY
    elif day_offset > 0:
        current_period = 0

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
    previous_starts: dict[int, int] = {}

    for sb, behavior in all_items:
        # One problem entry per behaviour, not per scheduled session: a behaviour
        # scheduled twice must not become two independent planners' behaviours,
        # which would double its minutes and break its duration bounds.
        if behavior.id not in behavior_index_map:
            behavior_index_map[behavior.id] = len(behaviors_db)
            behaviors_db.append(behavior)
        idx = behavior_index_map[behavior.id]
        local_period = sb.time_period % PERIODS_PER_DAY
        blocks = sb.scheduled_duration // 15
        for b in range(blocks):
            t = local_period + b
            if t < current_period:
                frozen_periods.setdefault(idx, {})[t] = (
                    1 if behavior.id in completed_ids else 0
                )

    for sb, behavior in all_items:
        # The session each behaviour carries into the re-plan: its earliest
        # session that has not fully elapsed. In-progress sessions count from
        # now, so keeping them still reports no disruption.
        idx = behavior_index_map[behavior.id]
        local_start = sb.time_period % PERIODS_PER_DAY
        if local_start + sb.scheduled_duration // 15 > current_period:
            ref = max(local_start, current_period)
            if idx not in previous_starts or ref < previous_starts[idx]:
                previous_starts[idx] = ref

    # 5. Build problem
    obj_result = await db.execute(
        sa_select(Objective).where(Objective.user_id == current_user.id)
    )
    objectives_db = obj_result.scalars().all()
    raw_weights = {
        o.type.value if hasattr(o.type, "value") else str(o.type): o.weight
        for o in objectives_db
    }
    # One normalised distribution reaches the solver; the raw weights are kept
    # for the plan's audit record (docs/FORMULATION.md).
    objectives = normalise_weights(raw_weights)

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
                protected=bool(getattr(b, "is_protected", False)),
            )
            for b in behaviors_db
        ],
        objectives=objectives,
        constraints=constraints,
        start_date=target_date,
        end_date=target_date,
        time_periods=PERIODS_PER_DAY,
    )
    # Commitments occupy fixed time today too; a re-plan must plan around them
    # (they are how a commitment displaces habits mid-day, docs/ITEMS.md).
    from app.services.items import blocked_periods_for_day

    problem.blocked_periods = frozenset(
        await blocked_periods_for_day(db, current_user, target_date)
    )

    # 6. Solve
    new_run_id = _uuid4()
    solver = CandidateSolver(timeout_seconds=30)
    solution = await run_in_solver_pool(
        solver.solve_partial_day,
        problem,
        new_run_id,
        frozen_periods,
        timeout_seconds=30,
        previous_starts=previous_starts,
    )

    if solution.status == "protected_conflict":
        conflict = (solution.diagnostics or {}).get("protected_conflict") or {}
        raise HTTPException(
            status_code=409,
            detail={
                "code": "protected_conflict",
                "message": (
                    "A protected habit cannot be placed in the rest of the day; "
                    "release a session or shorten the habit."
                ),
                "unplaced": conflict.get("unplaced", []),
                "conflicting": conflict.get("conflicting", []),
                "minimalRelaxation": conflict.get("minimalRelaxation", []),
            },
        )

    # 7. Persist as the next revision, keeping session identity (METRIC.md §4).
    # Drafts before the baseline freezes stay revision 1 and retire nothing; a
    # re-plan of a frozen baseline is a new revision that retires what it drops.
    plan = await resolve_day_plan(db, current_user, target_date)
    previous_run = plan.run
    frozen = previous_run is not None and plan.frozen
    revision = ((previous_run.plan_revision or 1) + 1) if frozen else 1

    previous_sessions: list[ScheduledBehavior] = []
    if previous_run is not None:
        prev_result = await db.execute(
            sa_select(ScheduledBehavior)
            .where(ScheduledBehavior.optimization_run_id == previous_run.id)
            .order_by(ScheduledBehavior.time_period)
        )
        previous_sessions = list(prev_result.scalars().all())

    previous_by_behavior: dict[UUID, list[ScheduledBehavior]] = {}
    for sb in previous_sessions:
        previous_by_behavior.setdefault(sb.behavior_id, []).append(sb)

    new_run = OptimizationRun(
        id=new_run_id,
        user_id=current_user.id,
        status="completed" if solution.status == "optimal" else "feasible",
        # Variant (full/partial/forced) stays in results + diagnostics.
        solver="candidate",
        start_date=target_date,
        end_date=target_date,
        time_periods=PERIODS_PER_DAY,
        total_objective_value=solution.total_objective_value,
        results=solution.to_dict(),
        diagnostics={
            **(solution.diagnostics or {}),
            "objective_weights": record_weights(raw_weights),
        },
        plan_revision=revision,
    )
    db.add(new_run)

    items_by_behavior: dict[UUID, list] = {}
    for item in solution.schedule_items:
        items_by_behavior.setdefault(item.behavior_id, []).append(item)

    for behavior_id, items in items_by_behavior.items():
        items.sort(key=lambda item: item.time_period)
        previous = previous_by_behavior.get(behavior_id, [])
        for index, item in enumerate(items):
            # A surviving session keeps its id even when it moved.
            planned_session_id = (
                previous[index].planned_session_id if index < len(previous) else uuid4()
            )
            db.add(ScheduledBehavior(
                optimization_run_id=new_run_id,
                behavior_id=item.behavior_id,
                time_period=item.time_period,
                scheduled_duration=item.scheduled_duration,
                is_scheduled=item.is_scheduled,
                planned_session_id=planned_session_id,
                plan_revision=revision,
            ))
        if frozen:
            # Dropped sessions are retired, never deleted or renumbered.
            for leftover in previous[len(items):]:
                leftover.retired_revision = revision

    if frozen:
        # Behaviours missing from the new plan entirely (declined, not merely
        # shortened) never enter the loop above; their sessions retire too.
        for behavior_id, previous in previous_by_behavior.items():
            if behavior_id not in items_by_behavior:
                for leftover in previous:
                    leftover.retired_revision = revision

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
            "disruption": (solution.diagnostics or {}).get("stability"),
        },
        message="Partial re-optimization completed",
    )
