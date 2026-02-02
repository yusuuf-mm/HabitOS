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
from app.schemas.api import ApiResponse
from app.schemas.optimization import (
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


async def map_run_to_response(db: AsyncSession, run: OptimizationRun, user: User) -> OptimizationRunResponse:
    """Map OptimizationRun model to OptimizationRunResponse schema."""
    # Fetch scheduled behaviors with their behavior details
    scheduled_result = await db.execute(
        select(ScheduledBehavior, Behavior)
        .join(Behavior)
        .where(ScheduledBehavior.optimization_run_id == run.id)
    )
    scheduled_items = scheduled_result.all()
    
    objective_map = await get_objective_map(db, user.id)
    
    scheduled_behaviors = []
    for s, b in scheduled_items:
        # Simplistic mapping of time_period to a TimeSlot or name
        # In a real app, this should be more consistent
        scheduled_behaviors.append(
            ScheduledBehaviorResponse(
                id=s.id,
                behaviorId=s.behavior_id,
                behavior=map_behavior_to_response(b, objective_map=objective_map),
                scheduledDate=run.start_date, # Or derive from time_period
                timeSlot="morning", # Placeholder
                startTime="09:00",  # Placeholder
                endTime="10:00",    # Placeholder
                duration=s.scheduled_duration,
                isCompleted=False,
            )
        )

    # Reconstruct contributions from results JSON
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

    return OptimizationRunResponse(
        id=run.id,
        user_id=run.user_id,
        status=run.status.value if hasattr(run.status, "value") else str(run.status),
        solver_status=run.results.get("status") if run.results else None,
        scheduled_behaviors=scheduled_behaviors,
        objective_contributions=contributions,
        total_score=run.total_objective_value or 0.0,
        execution_time_ms=int((run.execution_time_seconds or 0) * 1000),
        constraints_satisfied=0, # Placeholder
        constraints_total=0,     # Placeholder
        created_at=run.created_at,
        completed_at=run.updated_at,
    )


@router.post("/solve", response_model=ApiResponse[OptimizationResult])
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
                preferred_time_slots=[s.value if hasattr(s, "value") else s for s in b.preferred_time_slots],
            )
            for b in behaviors_db
        ]

        objectives = {obj.type.value if hasattr(obj.type, "value") else str(obj.type): obj.weight for obj in objectives_db}

        constraints = [
            ConstraintInput(
                type=c.type.value if hasattr(c.type, "value") else str(c.type),
                parameters=c.parameters,
                is_active=c.is_active,
            )
            for c in constraints_db
        ]

        # Determine time periods and dates
        start_date = request.targetDate or date_class.today()
        # For simplicity, optimize for 1 day if not specified. Original was session setting.
        time_periods = 1
        end_date = start_date

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
        await db.refresh(run)

        # Build response using helper
        run_response = await map_run_to_response(db, run, current_user)
        
        return ApiResponse(
            data=OptimizationResult(run=run_response),
            message="Optimization completed successfully"
        ).dict(exclude_none=True)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Optimization error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Optimization failed: {str(e)}",
        )


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
        items.append(await map_run_to_response(db, run, current_user))

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

    run_response = await map_run_to_response(db, run, current_user)
    
    return ApiResponse(
        data=OptimizationResult(run=run_response)
    ).dict(exclude_none=True)
