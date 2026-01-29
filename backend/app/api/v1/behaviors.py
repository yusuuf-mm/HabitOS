"""Behavior routes."""
import logging
from typing import List
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_db, get_current_active_user
from app.models import User, Behavior, CompletionLog, Objective
from app.schemas import (
    BehaviorCreate,
    BehaviorUpdate,
    BehaviorResponse,
    BehaviorListResponse,
    BehaviorStatistics,
    BehaviorImpacts,
    PaginationParams,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/behaviors", tags=["behaviors"])


@router.get("", response_model=BehaviorListResponse)
async def list_behaviors(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
) -> dict:
    """List user's behaviors."""
    # Get total count
    result = await db.execute(
        select(func.count(Behavior.id)).where(Behavior.user_id == current_user.id)
    )
    total = result.scalar() or 0

    # Get paginated behaviors
    result = await db.execute(
        select(Behavior)
        .where(Behavior.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
    )
    behaviors = result.scalars().all()

    # Build responses with statistics
    items = []
    for behavior in behaviors:
        stats_result = await db.execute(
            select(
                func.count(CompletionLog.id).label("total_completions"),
                func.avg(CompletionLog.actual_duration).label("avg_duration"),
                func.avg(CompletionLog.satisfaction_score).label("avg_satisfaction"),
                func.max(CompletionLog.completed_at).label("last_completed"),
                func.sum(CompletionLog.actual_duration).label("total_duration"),
            ).where(CompletionLog.behavior_id == behavior.id)
        )
        stats = stats_result.first()

        item_response = BehaviorResponse(
            id=behavior.id,
            name=behavior.name,
            description=behavior.description,
            category=behavior.category.value,
            min_duration=behavior.min_duration,
            typical_duration=behavior.typical_duration,
            max_duration=behavior.max_duration,
            energy_cost=behavior.energy_cost,
            is_active=behavior.is_active,
            preferred_time_slots=[s.value for s in behavior.preferred_time_slots],
            impacts=BehaviorImpacts(
                health=behavior.impact_on_health,
                productivity=behavior.impact_on_productivity,
                learning=behavior.impact_on_learning,
                wellness=behavior.impact_on_wellness,
                social=behavior.impact_on_social,
            ),
            created_at=behavior.created_at,
            updated_at=behavior.updated_at,
            statistics=BehaviorStatistics(
                total_completions=stats[0] or 0,
                avg_duration=stats[1],
                avg_satisfaction=stats[2],
                last_completed=stats[3],
                total_duration=int(stats[4] or 0),
            ),
        )
        items.append(item_response)

    return {
        "data": items,
        "success": True,
        "message": f"Retrieved {len(items)} behaviors",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("", response_model=BehaviorResponse, status_code=201)
async def create_behavior(
    request: BehaviorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Create a new behavior."""
    from uuid import uuid4
    behavior = Behavior(
        id=uuid4(),
        user_id=current_user.id,
        name=request.name,
        description=request.description,
        category=request.category,
        min_duration=request.min_duration,
        typical_duration=request.typical_duration,
        max_duration=request.max_duration,
        energy_cost=request.energy_cost,
        preferred_time_slots=request.preferred_time_slots or ["flexible"],
        impact_on_health=request.impacts.health,
        impact_on_productivity=request.impacts.productivity,
        impact_on_learning=request.impacts.learning,
        impact_on_wellness=request.impacts.wellness,
        impact_on_social=request.impacts.social,
    )
    db.add(behavior)
    await db.commit()
    await db.refresh(behavior)

    return BehaviorResponse(
        id=behavior.id,
        name=behavior.name,
        description=behavior.description,
        category=behavior.category.value,
        min_duration=behavior.min_duration,
        typical_duration=behavior.typical_duration,
        max_duration=behavior.max_duration,
        energy_cost=behavior.energy_cost,
        is_active=behavior.is_active,
        preferred_time_slots=[s.value for s in behavior.preferred_time_slots],
        impacts=BehaviorImpacts(
            health=behavior.impact_on_health,
            productivity=behavior.impact_on_productivity,
            learning=behavior.impact_on_learning,
            wellness=behavior.impact_on_wellness,
            social=behavior.impact_on_social,
        ),
        created_at=behavior.created_at,
        updated_at=behavior.updated_at,
    )



@router.get("/objectives", response_model=dict)
async def list_objectives(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """List user objectives."""
    result = await db.execute(
        select(Objective).where(Objective.user_id == current_user.id)
    )
    objectives = result.scalars().all()

    return {
        "data": [
            {
                "id": str(obj.id),
                "userId": str(obj.user_id),
                "name": obj.type.value,
                "description": obj.description,
                "priority": int(obj.weight * 10),  # Map weight 0-1 to priority 1-10
                "createdAt": obj.created_at.isoformat(),
            }
            for obj in objectives
        ],
        "success": True,
        "message": "Objectives retrieved successfully",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/{behavior_id}", response_model=BehaviorResponse)
async def get_behavior(
    behavior_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Get a specific behavior."""
    result = await db.execute(
        select(Behavior).where(
            (Behavior.id == behavior_id) & (Behavior.user_id == current_user.id)
        )
    )
    behavior = result.scalars().first()

    if not behavior:
        raise HTTPException(status_code=404, detail="Behavior not found")

    return BehaviorResponse(
        id=behavior.id,
        name=behavior.name,
        description=behavior.description,
        category=behavior.category.value,
        min_duration=behavior.min_duration,
        typical_duration=behavior.typical_duration,
        max_duration=behavior.max_duration,
        energy_cost=behavior.energy_cost,
        is_active=behavior.is_active,
        preferred_time_slots=[s.value for s in behavior.preferred_time_slots],
        impacts=BehaviorImpacts(
            health=behavior.impact_on_health,
            productivity=behavior.impact_on_productivity,
            learning=behavior.impact_on_learning,
            wellness=behavior.impact_on_wellness,
            social=behavior.impact_on_social,
        ),
        created_at=behavior.created_at,
        updated_at=behavior.updated_at,
    )


@router.put("/{behavior_id}", response_model=BehaviorResponse)
async def update_behavior(
    behavior_id: UUID,
    request: BehaviorUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Update a behavior."""
    result = await db.execute(
        select(Behavior).where(
            (Behavior.id == behavior_id) & (Behavior.user_id == current_user.id)
        )
    )
    behavior = result.scalars().first()

    if not behavior:
        raise HTTPException(status_code=404, detail="Behavior not found")

    # Update fields
    if request.name is not None:
        behavior.name = request.name
    if request.description is not None:
        behavior.description = request.description
    if request.category is not None:
        behavior.category = request.category
    if request.min_duration is not None:
        behavior.min_duration = request.min_duration
    if request.typical_duration is not None:
        behavior.typical_duration = request.typical_duration
    if request.max_duration is not None:
        behavior.max_duration = request.max_duration
    if request.energy_cost is not None:
        behavior.energy_cost = request.energy_cost
    if request.preferred_time_slots is not None:
        behavior.preferred_time_slots = request.preferred_time_slots
    if request.impacts is not None:
        behavior.impact_on_health = request.impacts.health
        behavior.impact_on_productivity = request.impacts.productivity
        behavior.impact_on_learning = request.impacts.learning
        behavior.impact_on_wellness = request.impacts.wellness
        behavior.impact_on_social = request.impacts.social

    await db.commit()
    await db.refresh(behavior)

    return BehaviorResponse(
        id=behavior.id,
        name=behavior.name,
        description=behavior.description,
        category=behavior.category.value,
        min_duration=behavior.min_duration,
        typical_duration=behavior.typical_duration,
        max_duration=behavior.max_duration,
        energy_cost=behavior.energy_cost,
        is_active=behavior.is_active,
        preferred_time_slots=[s.value for s in behavior.preferred_time_slots],
        impacts=BehaviorImpacts(
            health=behavior.impact_on_health,
            productivity=behavior.impact_on_productivity,
            learning=behavior.impact_on_learning,
            wellness=behavior.impact_on_wellness,
            social=behavior.impact_on_social,
        ),
        created_at=behavior.created_at,
        updated_at=behavior.updated_at,
    )


@router.delete("/{behavior_id}", status_code=204)
async def delete_behavior(
    behavior_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """Delete a behavior."""
    result = await db.execute(
        select(Behavior).where(
            (Behavior.id == behavior_id) & (Behavior.user_id == current_user.id)
        )
    )
    behavior = result.scalars().first()

    if not behavior:
        raise HTTPException(status_code=404, detail="Behavior not found")

    await db.delete(behavior)
    await db.commit()
