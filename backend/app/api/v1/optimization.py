"""Optimization routes."""
import logging
from datetime import datetime, timezone, date as date_class
from uuid import uuid4, UUID
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_db, get_current_active_user
from app.core import settings
from app.core.constants import period_to_time, PERIODS_PER_DAY
from app.services.metrics import local_today, resolve_day_plan, user_zone
from app.models import (
    User,
    Behavior,
    Objective,
    Constraint,
    OptimizationRun,
    ScheduledBehavior,
)
from app.core.exceptions import (
    InfeasibleProblemError,
    SolverBusyError,
    SolverError,
    SolverTimeoutError,
    UnboundedProblemError,
)
from app.optimization import (
    CandidateSolver,
    OptimizationProblem,
    BehaviorScheduleInput,
    ConstraintInput,
    normalise_weights,
    record_weights,
    run_in_solver_pool,
)
from app.schemas.api import ApiResponse
from app.schemas.optimization import (
    ForcedIncludeRequest,
    ForcedIncludeResult,
    ForcedSession,
    DisplacedSession,
    OptimizationRequest,
    OptimizationResult,
    OptimizationRunResponse,
    OptimizationHistoryResponse,
    ScheduledBehaviorResponse,
    ObjectiveContributionSchema,
)
from app.api.v1.behaviors import map_behavior_to_response, get_objective_map

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/optimization", tags=["optimization"])

# Production builds the candidate-placement formulation. The module-level name
# stays ``LinearSolver`` because callers (and failure-path tests) patch that
# attribute to substitute a solver; what it resolves to is the shipped model.
LinearSolver = CandidateSolver


async def _load_problem(
    db: AsyncSession, user: User, target_date: date_class
):
    """Build the day's optimization problem from the user's stored data.

    Weights are normalised here, once: the solver only ever sees a distribution
    summing to 1, and the raw values are returned so the plan can record both.
    """
    behaviors_result = await db.execute(
        select(Behavior).where(
            (Behavior.user_id == user.id) & (Behavior.is_active == True)
        )
    )
    behaviors_db = behaviors_result.scalars().all()
    if not behaviors_db:
        raise HTTPException(
            status_code=422,
            detail="No active behaviors found. Please create behaviors first.",
        )

    objectives_result = await db.execute(
        select(Objective).where(Objective.user_id == user.id)
    )
    objectives_db = objectives_result.scalars().all()
    if not objectives_db:
        raise HTTPException(
            status_code=422,
            detail="No objectives found. Please set objectives first.",
        )

    constraints_result = await db.execute(
        select(Constraint).where(
            (Constraint.user_id == user.id) & (Constraint.is_active == True)
        )
    )
    constraints_db = constraints_result.scalars().all()

    behaviors = [
        BehaviorScheduleInput(
            id=b.id,
            name=b.name,
            min_duration=b.min_duration,
            typical_duration=b.typical_duration,
            max_duration=b.max_duration,
            energy_cost=b.energy_cost,
            impacts=b.get_all_impacts(),
            preferred_time_slots=[
                s.value if hasattr(s, "value") else s for s in b.preferred_time_slots
            ],
        )
        for b in behaviors_db
    ]

    raw_weights = {
        obj.type.value if hasattr(obj.type, "value") else str(obj.type): obj.weight
        for obj in objectives_db
    }

    constraints = [
        ConstraintInput(
            type=c.type.value if hasattr(c.type, "value") else str(c.type),
            parameters=c.parameters,
            is_active=c.is_active,
        )
        for c in constraints_db
    ]

    problem = OptimizationProblem(
        user_id=user.id,
        behaviors=behaviors,
        objectives=normalise_weights(raw_weights),
        constraints=constraints,
        start_date=target_date,
        end_date=target_date,
        time_periods=PERIODS_PER_DAY,
    )
    return problem, raw_weights


async def map_run_to_response(db: AsyncSession, run: OptimizationRun, user: User, include_schedule: bool = True) -> OptimizationRunResponse:
    """Map OptimizationRun model to OptimizationRunResponse schema."""
    # Fetch scheduled behaviors with their behavior details
    scheduled_result = await db.execute(
        select(ScheduledBehavior, Behavior)
        .join(Behavior)
        .where(ScheduledBehavior.optimization_run_id == run.id)
        .order_by(ScheduledBehavior.time_period)
    )
    scheduled_items = scheduled_result.all()
    
    objective_map = await get_objective_map(db, user.id)

    scheduled_behaviors = []
    total_duration = 0
    for s, b in scheduled_items:
        duration = s.scheduled_duration
        start_time = period_to_time(s.time_period)
        end_time = period_to_time(s.time_period + (duration // 15))
        
        scheduled_behaviors.append(
            ScheduledBehaviorResponse(
                id=s.id,
                behaviorId=s.behavior_id,
                behavior=map_behavior_to_response(b, objective_map=objective_map),
                scheduledDate=run.start_date,
                timeSlot="flexible", # Standardized for generated schedule
                startTime=start_time,
                endTime=end_time,
                duration=duration,
                isCompleted=False, # Default for new runs
            )
        )
        total_duration += duration

    # Reconstruct contributions from results JSON.
    # The solver stores ``contribution`` and ``weight`` but not ``percentage``,
    # so we compute it here as each objective's share of total objective value.
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

    run_response = OptimizationRunResponse(
        id=run.id,
        user_id=run.user_id,
        status=run.status.value if hasattr(run.status, "value") else str(run.status),
        solver_status=run.results.get("status") if run.results else None,
        scheduled_behaviors=scheduled_behaviors,
        objective_contributions=contributions,
        total_score=run.total_objective_value or 0.0,
        execution_time_ms=int((run.execution_time_seconds or 0) * 1000),
        constraints_satisfied=len(scheduled_behaviors), # Simplified
        constraints_total=len(scheduled_behaviors),    # Simplified
        created_at=run.created_at,
        completed_at=run.updated_at,
    )
    
    if not include_schedule:
        return run_response

    from app.schemas.schedule import DailySchedule
    schedule = DailySchedule(
        id=run.id,
        user_id=user.id,
        date=run.start_date,
        scheduled_behaviors=scheduled_behaviors,
        total_duration=total_duration,
        objective_scores=contributions,
        created_at=run.created_at,
    )
    
    return run_response, schedule


@router.post("/solve", response_model=ApiResponse[OptimizationResult])
async def solve_optimization(
    request: OptimizationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Solve optimization problem for user."""
    try:
        # Once today's baseline is frozen, a fresh plan would be a plan the metric
        # cannot count and the user did not ask for: re-planning is the way to
        # change today. Future days are unaffected (docs/METRIC.md §2).
        tz = user_zone(current_user)
        today_local = local_today(tz)
        start_date = request.targetDate or today_local
        if start_date == today_local:
            plan = await resolve_day_plan(db, current_user, today_local)
            if plan.frozen:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "baseline is set; use re-plan "
                        "(POST /api/v1/schedule/reoptimize) instead of generating a new plan."
                    ),
                )

        problem, raw_weights = await _load_problem(db, current_user, start_date)

        # Solve
        optimization_run_id = uuid4()
        solver = LinearSolver(timeout_seconds=settings.OPTIMIZATION_TIMEOUT_SECONDS)
        solution = await run_in_solver_pool(
            solver.solve,
            problem,
            optimization_run_id,
            timeout_seconds=settings.OPTIMIZATION_TIMEOUT_SECONDS,
        )

        # Save to database
        run = OptimizationRun(
            id=optimization_run_id,
            user_id=current_user.id,
            status="completed" if solution.status == "optimal" else "feasible",
            # The column is a coarse enum (linear/heuristic/...); the exact
            # formulation is recorded in results + diagnostics instead.
            solver="linear",
            start_date=start_date,
            end_date=start_date,
            time_periods=PERIODS_PER_DAY,
            total_objective_value=solution.total_objective_value,
            execution_time_seconds=solution.execution_time_seconds,
            results=solution.to_dict(),
            diagnostics={
                **(solution.diagnostics or {}),
                "objective_weights": record_weights(raw_weights),
            },
        )
        db.add(run)

        # Save scheduled behaviors
        for item in solution.schedule_items:
            scheduled = ScheduledBehavior(
                optimization_run_id=optimization_run_id,
                behavior_id=item.behavior_id,
                time_period=item.time_period,
                scheduled_duration=item.scheduled_duration,
                is_scheduled=item.is_scheduled,
            )
            db.add(scheduled)

        await db.commit()
        await db.refresh(run)

        # Build response using helper
        run_response, schedule = await map_run_to_response(db, run, current_user)
        
        return ApiResponse(
            data=OptimizationResult(run=run_response, schedule=schedule),
            message="Optimization completed successfully"
        ).dict(exclude_none=True)

    except HTTPException:
        raise
    except SolverBusyError as exc:
        logger.info("Solver pool busy: %s", exc.detail)
        raise HTTPException(
            status_code=503,
            detail=exc.detail,
            headers={"Retry-After": "2"},
        )
    except (InfeasibleProblemError, UnboundedProblemError, SolverTimeoutError) as exc:
        # A solve that produced no trustworthy plan is a normal result, not a bug.
        logger.info("Solve produced no plan: %s", exc.detail)
        raise HTTPException(status_code=422, detail=exc.detail)
    except SolverError as exc:
        logger.error("Solver error: %s", exc.detail)
        raise HTTPException(status_code=422, detail=exc.detail)
    except Exception:
        logger.exception("Optimization error")
        raise HTTPException(status_code=500, detail="Optimization failed")


@router.get("/history", response_model=ApiResponse[OptimizationHistoryResponse])
async def get_optimization_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
) -> dict:
    """Get optimization run history."""
    # Get total count
    result = await db.execute(
        select(func.count(OptimizationRun.id)).where(
            OptimizationRun.user_id == current_user.id
        )
    )
    total = result.scalar() or 0

    # Get paginated runs
    result = await db.execute(
        select(OptimizationRun)
        .where(OptimizationRun.user_id == current_user.id)
        .order_by(OptimizationRun.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    runs = result.scalars().all()

    items = []
    for run in runs:
        run_response = await map_run_to_response(db, run, current_user, include_schedule=False)
        items.append(run_response)

    return ApiResponse(
        data=OptimizationHistoryResponse(
            total=total,
            skip=skip,
            limit=limit,
            data=items
        ),
        message=f"Retrieved {len(items)} optimization runs"
    ).dict(exclude_none=True)


@router.get("/history/{optimization_run_id}", response_model=ApiResponse[OptimizationResult])
async def get_optimization_run(
    optimization_run_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Get a specific optimization run with full details."""
    result = await db.execute(
        select(OptimizationRun).where(
            (OptimizationRun.id == optimization_run_id) &
            (OptimizationRun.user_id == current_user.id)
        )
    )
    run = result.scalars().first()

    if not run:
        raise HTTPException(status_code=404, detail="Optimization run not found")

    run_response, schedule = await map_run_to_response(db, run, current_user)
    
    return ApiResponse(
        data=OptimizationResult(run=run_response, schedule=schedule)
    ).dict(exclude_none=True)
@router.post("/forced-include", response_model=ApiResponse[ForcedIncludeResult])
async def forced_include(
    request: ForcedIncludeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """What would it cost to fit these behaviours into the day?

    Runs a what-if solve with the named behaviours forced in, at lower priority
    than a real plan (it never takes the last free worker). Returns the forced
    sessions, what had to give way, the change in the plan's value, and the
    relaxations that would be needed if the behaviours cannot fit at all.
    """
    try:
        if not request.behaviorIds:
            raise HTTPException(
                status_code=422,
                detail="Name at least one behaviour to force in.",
            )

        tz = user_zone(current_user)
        target_date = request.targetDate or local_today(tz)
        problem, raw_weights = await _load_problem(db, current_user, target_date)

        known = {b.id for b in problem.behaviors}
        unknown = [str(b) for b in request.behaviorIds if b not in known]
        if unknown:
            raise HTTPException(
                status_code=404,
                detail="Behaviour not found or inactive: " + ", ".join(unknown),
            )
        forced_ids = set(request.behaviorIds)

        solver = LinearSolver(timeout_seconds=settings.OPTIMIZATION_TIMEOUT_SECONDS)
        timeout = settings.OPTIMIZATION_TIMEOUT_SECONDS

        baseline = await run_in_solver_pool(
            solver.solve,
            problem,
            uuid4(),
            timeout_seconds=timeout,
            low_priority=True,
        )

        try:
            solution = await run_in_solver_pool(
                solver.solve_forced,
                problem,
                uuid4(),
                request.behaviorIds,
                timeout_seconds=timeout,
                low_priority=True,
            )
        except InfeasibleProblemError as exc:
            return ApiResponse(
                data=ForcedIncludeResult(
                    fits=False,
                    forced=[],
                    displaced=[],
                    relaxations=[
                        {
                            "kind": "no_free_window",
                            "behaviorId": str(b),
                            "detail": "no free window is long enough to fit this behaviour",
                        }
                        for b in request.behaviorIds
                    ],
                    objectiveChange=0.0,
                    solverObjective=None,
                    seconds=0.0,
                    reason=exc.detail,
                ),
                message="These behaviours cannot be added to this day",
            ).dict(exclude_none=True)

        baseline_minutes = {}
        for item in baseline.schedule_items:
            baseline_minutes[item.behavior_id] = (
                baseline_minutes.get(item.behavior_id, 0) + item.scheduled_duration
            )

        by_id = {b.id: b for b in problem.behaviors}
        forced_sessions = [
            ForcedSession(
                behaviorId=item.behavior_id,
                behaviorName=item.behavior_name,
                startTime=period_to_time(item.time_period),
                endTime=period_to_time(
                    item.time_period + item.scheduled_duration // 15
                ),
                duration=item.scheduled_duration,
            )
            for item in solution.schedule_items
            if item.behavior_id in forced_ids
        ]

        displaced = [
            DisplacedSession(
                behaviorId=UUID(decline["behaviorId"]),
                behaviorName=decline["behaviorName"],
                reason=decline["reason"],
                minutes=baseline_minutes.get(UUID(decline["behaviorId"]), 0),
            )
            for decline in (solution.diagnostics or {}).get("declines", [])
        ]

        relaxations = [
            {
                "kind": "displaced",
                "behaviorId": str(item.behaviorId),
                "detail": f"'{item.behaviorName}' loses its {item.minutes} min session",
            }
            for item in displaced
        ]
        for item in solution.schedule_items:
            if item.behavior_id not in forced_ids:
                continue
            behavior = by_id[item.behavior_id]
            if item.scheduled_duration < behavior.max_duration:
                relaxations.append(
                    {
                        "kind": "shorten",
                        "behaviorId": str(item.behavior_id),
                        "detail": (
                            f"'{item.behavior_name}' is placed at "
                            f"{item.scheduled_duration} min instead of up to "
                            f"{behavior.max_duration} min"
                        ),
                    }
                )

        value_change = (solution.total_objective_value or 0.0) - (
            baseline.total_objective_value or 0.0
        )

        return ApiResponse(
            data=ForcedIncludeResult(
                fits=True,
                forced=forced_sessions,
                displaced=displaced,
                relaxations=relaxations,
                objectiveChange=round(value_change, 4),
                solverObjective=(solution.diagnostics or {}).get("solver_objective"),
                seconds=solution.execution_time_seconds or 0.0,
                reason=None,
            ),
            message="Forced-include solve completed",
        ).dict(exclude_none=True)

    except HTTPException:
        raise
    except SolverBusyError as exc:
        logger.info("Solver pool busy: %s", exc.detail)
        raise HTTPException(
            status_code=503,
            detail=exc.detail,
            headers={"Retry-After": "2"},
        )
    except (InfeasibleProblemError, UnboundedProblemError, SolverTimeoutError) as exc:
        logger.info("Forced solve produced no plan: %s", exc.detail)
        raise HTTPException(status_code=422, detail=exc.detail)
    except SolverError as exc:
        logger.error("Forced solve error: %s", exc.detail)
        raise HTTPException(status_code=422, detail=exc.detail)
    except Exception:
        logger.exception("Forced-include error")
        raise HTTPException(status_code=500, detail="Forced-include solve failed")
