"""Build one day's optimization problem from the user's stored settings.

Extracted from the solve route so the normal solve, what-if endpoints and the
week planner all build the same problem: same active behaviours, same saved
objective weights, same active constraints and the same commitment blocks.
"""

from datetime import date as date_class

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import PERIODS_PER_DAY
from app.models import Behavior, Constraint, Objective, User
from app.optimization import (
    BehaviorScheduleInput,
    ConstraintInput,
    OptimizationProblem,
    normalise_weights,
)
from app.services.items import blocked_periods_for_day


async def load_day_problem(
    db: AsyncSession, user: User, target_date: date_class
) -> tuple[OptimizationProblem, dict]:
    """Build the day's problem and return it with the raw saved weights.

    Weights are normalised here, once: the solver only ever sees a distribution
    summing to 1, while the raw values stay available for the plan's audit record.
    """
    behaviors_result = await db.execute(
        select(Behavior).where(
            (Behavior.user_id == user.id) & Behavior.is_active.is_(True)
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
            (Constraint.user_id == user.id) & Constraint.is_active.is_(True)
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
            protected=bool(getattr(b, "is_protected", False)),
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
    # Commitments occupy fixed time on this date (docs/ITEMS.md): the solver
    # plans around them. Private items are included by blocked_periods_for_day.
    problem.blocked_periods = frozenset(
        await blocked_periods_for_day(db, user.id, target_date)
    )
    return problem, raw_weights
