"""Optimization routes."""
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_db, get_current_active_user
from app.core import settings
from app.models import (
    User,
    Behavior,
    Objective,
    Constraint,
    OptimizationRun,
    ScheduledBehavior,
)
from app.optimization import (
    LinearSolver,
    OptimizationProblem,
    BehaviorScheduleInput,
    ConstraintInput,
)
from app.schemas import (
    OptimizationRequest,
    OptimizationResult,
    OptimizationHistoryResponse,
    OptimizationSummary,
    ScheduledBehaviorResponse,
    ObjectiveContributionsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/optimization", tags=["optimization"])


@router.post("/solve", response_model=OptimizationResult)
async def solve_optimization(
    request: OptimizationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Solve optimization problem for user."""
    try:
        # Load user data
        behaviors_result = await db.execute(
            select(Behavior).where(
                (Behavior.user_id == current_user.id) & (Behavior.is_active == True)
            )
        )
        behaviors_db = behaviors_result.scalars().all()

        if not behaviors_db:
            raise HTTPException(
                status_code=422,
                detail="No active behaviors found. Please create behaviors first.",
            )

        objectives_result = await db.execute(
            select(Objective).where(Objective.user_id == current_user.id)
        )
        objectives_db = objectives_result.scalars().all()

        if not objectives_db:
            raise HTTPException(
                status_code=422,
                detail="No objectives found. Please set objectives first.",
            )

        constraints_result = await db.execute(
            select(Constraint).where(
                (Constraint.user_id == current_user.id) & (Constraint.is_active == True)
            )
        )
        constraints_db = constraints_result.scalars().all()

        # Convert to optimization inputs
        behaviors = [
            BehaviorScheduleInput(
                id=b.id,
                name=b.name,
                min_duration=b.min_duration,
                typical_duration=b.typical_duration,
                max_duration=b.max_duration,
                energy_cost=b.energy_cost,
                impacts=b.get_all_impacts(),
                preferred_time_slots=[s.value for s in b.preferred_time_slots],
            )
            for b in behaviors_db
        ]

        objectives = {obj.type.value: obj.weight for obj in objectives_db}

        constraints = [
            ConstraintInput(
                type=c.type.value,
                parameters=c.parameters,
                is_active=c.is_active,
            )
            for c in constraints_db
        ]

        # Determine time periods
        time_periods = request.time_periods or settings.OPTIMIZATION_TIME_PERIODS
        start_date = request.start_date
        end_date = request.end_date

        # Create optimization problem
        problem = OptimizationProblem(
            user_id=current_user.id,
            behaviors=behaviors,
            objectives=objectives,
            constraints=constraints,
            start_date=start_date,
            end_date=end_date,
            time_periods=time_periods,
        )

        # Solve
        optimization_run_id = uuid4()
        solver = LinearSolver(timeout_seconds=settings.OPTIMIZATION_TIMEOUT_SECONDS)
        solution = solver.solve(problem, optimization_run_id)

        # Save to database
        run = OptimizationRun(
            id=optimization_run_id,
            user_id=current_user.id,
            status="completed" if solution.status == "optimal" else "feasible",
            solver="linear",
            start_date=start_date,
            end_date=end_date,
            time_periods=time_periods,
            total_objective_value=solution.total_objective_value,
            execution_time_seconds=solution.execution_time_seconds,
            results=solution.to_dict(),
            diagnostics=solution.diagnostics,
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

        # Build response
        return OptimizationResult(
            optimization_run_id=optimization_run_id,
            status=solution.status,
            solver=solution.solver,
            total_objective_value=solution.total_objective_value,
            total_scheduled_duration=solution.total_scheduled_duration,
            scheduled_behavior_count=solution.scheduled_behavior_count,
            execution_time_seconds=solution.execution_time_seconds,
            schedule_items=[
                ScheduledBehaviorResponse(
                    behavior_id=item.behavior_id,
                    behavior_name=item.behavior_name,
                    time_period=item.time_period,
                    scheduled_duration=item.scheduled_duration,
                    is_scheduled=item.is_scheduled,
                )
                for item in solution.schedule_items
            ],
            objective_contributions={
                obj_type: ObjectiveContributionsResponse(
                    objective_type=contrib.objective_type,
                    contribution=contrib.contribution,
                    weight=contrib.weight,
                )
                for obj_type, contrib in solution.objective_contributions.items()
            },
            diagnostics=solution.diagnostics,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Optimization error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Optimization failed: {str(e)}",
        )


@router.get("/history", response_model=OptimizationHistoryResponse)
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
        # Count behaviors in schedule
        scheduled_result = await db.execute(
            select(func.count(ScheduledBehavior.id)).where(
                ScheduledBehavior.optimization_run_id == run.id
            )
        )
        behaviors_scheduled = scheduled_result.scalar() or 0

        # Sum durations
        duration_result = await db.execute(
            select(func.sum(ScheduledBehavior.scheduled_duration)).where(
                ScheduledBehavior.optimization_run_id == run.id
            )
        )
        total_duration = duration_result.scalar() or 0

        items.append(
            OptimizationSummary(
                id=run.id,
                status=run.status.value,
                solver=run.solver.value,
                start_date=run.start_date,
                end_date=run.end_date,
                behaviors_scheduled=behaviors_scheduled,
                total_scheduled_duration=total_duration,
                total_objective_value=run.total_objective_value,
                execution_time_seconds=run.execution_time_seconds,
                created_at=run.created_at.isoformat(),
            )
        )

    return OptimizationHistoryResponse(
        total=total, skip=skip, limit=limit, items=items
    )
