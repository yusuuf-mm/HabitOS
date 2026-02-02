"""Behavior routes."""
import logging
from typing import List, Dict
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_db, get_current_active_user
from app.models import User, Behavior, CompletionLog, Objective
from app.schemas.api import ApiResponse
from app.schemas.behavior import (
    BehaviorCreate,
    BehaviorUpdate,
    BehaviorResponse,
    BehaviorListResponse,
    BehaviorStatistics,
    ObjectiveImpactCreate,
    ObjectiveImpactResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/behaviors", tags=["behaviors"])


async def get_objective_map(db: AsyncSession, user_id: UUID) -> Dict[str, UUID]:
    """Get mapping of objective type to its ID."""
    result = await db.execute(select(Objective).where(Objective.user_id == user_id))
    objectives = result.scalars().all()
    # Handle cases where objective names might be stored as enum values
    return {obj.type.value if hasattr(obj.type, "value") else str(obj.type): obj.id for obj in objectives}


def map_behavior_to_response(behavior: Behavior, stats: tuple = None, objective_map: Dict[str, UUID] = None) -> BehaviorResponse:
    """Map behavior model to BehaviorResponse schema."""
    impacts = []
    if objective_map:
        for obj_type, obj_id in objective_map.items():
            impact_score = behavior.get_impact(obj_type)
            if impact_score != 0:
                impacts.append(
                    ObjectiveImpactResponse(
                        objectiveId=obj_id,
                        objectiveName=obj_type.capitalize(),
                        impactScore=impact_score
                    )
                )

    statistics = None
    if stats:
        statistics = BehaviorStatistics(
            total_completions=stats[0] or 0,
            avg_duration=stats[1],
            avg_satisfaction=stats[2],
            last_completed=stats[3],
            total_duration=int(stats[4] or 0),
        )

    return BehaviorResponse(
        id=behavior.id,
        userId=behavior.user_id,
        name=behavior.name,
        description=behavior.description,
        category=behavior.category.value if hasattr(behavior.category, "value") else str(behavior.category),
        energyCost=behavior.energy_cost,
        durationMin=behavior.min_duration,
        durationMax=behavior.max_duration,
        preferredTimeSlots=[s.value if hasattr(s, "value") else str(s) for s in behavior.preferred_time_slots],
        objectiveImpacts=impacts,
        isActive=behavior.is_active,
        frequency=getattr(behavior, "frequency", "daily"),
        frequencyCount=getattr(behavior, "frequency_count", None),
        createdAt=behavior.created_at,
        updatedAt=behavior.updated_at,
        statistics=statistics,
    )


@router.get("", response_model=ApiResponse[BehaviorListResponse])
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
    
    objective_map = await get_objective_map(db, current_user.id)

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
        items.append(map_behavior_to_response(behavior, stats, objective_map))

    return ApiResponse(
        data=BehaviorListResponse(
            total=total,
            skip=skip,
            limit=limit,
            data=items
        ),
        message=f"Retrieved {len(items)} behaviors"
    ).dict(exclude_none=True)


@router.post("", response_model=ApiResponse[BehaviorResponse], status_code=201)
async def create_behavior(
    request: BehaviorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Create a new behavior."""
    behavior = Behavior(
        user_id=current_user.id,
        name=request.name,
        description=request.description,
        category=request.category,
        min_duration=request.durationMin,
        typical_duration=request.durationMin,  # Mapping to min since typical is gone in new schema
        max_duration=request.durationMax,
        energy_cost=request.energyCost,
        preferred_time_slots=request.preferredTimeSlots or ["flexible"],
        is_active=request.isActive,
    )
    
    # Map impacts from array to flat fields
    # We need objective types for this
    obj_result = await db.execute(select(Objective).where(Objective.user_id == current_user.id))
    objectives = {obj.id: obj.type.value if hasattr(obj.type, "value") else str(obj.type) for obj in obj_result.scalars().all()}
    
    if request.objectiveImpacts:
        for impact in request.objectiveImpacts:
            obj_type = objectives.get(impact.objectiveId)
            if obj_type == "health": behavior.impact_on_health = impact.impactScore
            elif obj_type == "productivity": behavior.impact_on_productivity = impact.impactScore
            elif obj_type == "learning": behavior.impact_on_learning = impact.impactScore
            elif obj_type == "wellness": behavior.impact_on_wellness = impact.impactScore
            elif obj_type == "social": behavior.impact_on_social = impact.impactScore

    db.add(behavior)
    await db.commit()
    await db.refresh(behavior)

    objective_map = {v: k for k, v in objectives.items()}
    return ApiResponse(
        data=map_behavior_to_response(behavior, objective_map=objective_map),
        message="Behavior created successfully"
    ).dict(exclude_none=True)


@router.get("/objectives", response_model=ApiResponse[List[dict]])
async def list_objectives(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """List user objectives."""
    result = await db.execute(
        select(Objective).where(Objective.user_id == current_user.id)
    )
    objectives = result.scalars().all()

    return ApiResponse(
        data=[
            {
                "id": str(obj.id),
                "userId": str(obj.user_id),
                "name": obj.type.value if hasattr(obj.type, "value") else str(obj.type),
                "description": obj.description,
                "priority": int((obj.weight or 0.5) * 10),
                "createdAt": obj.created_at.isoformat(),
            }
            for obj in objectives
        ],
        message="Objectives retrieved successfully"
    ).dict(exclude_none=True)


@router.get("/{behavior_id}", response_model=ApiResponse[BehaviorResponse])
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

    objective_map = await get_objective_map(db, current_user.id)
    return ApiResponse(
        data=map_behavior_to_response(behavior, objective_map=objective_map)
    ).dict(exclude_none=True)


@router.put("/{behavior_id}", response_model=ApiResponse[BehaviorResponse])
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
    if request.durationMin is not None:
        behavior.min_duration = request.durationMin
    if request.durationMax is not None:
        behavior.max_duration = request.durationMax
    if request.energyCost is not None:
        behavior.energy_cost = request.energyCost
    if request.preferredTimeSlots is not None:
        behavior.preferred_time_slots = request.preferredTimeSlots
    if request.isActive is not None:
        behavior.is_active = request.isActive

    if request.objectiveImpacts is not None:
        obj_result = await db.execute(select(Objective).where(Objective.user_id == current_user.id))
        objectives = {obj.id: obj.type.value if hasattr(obj.type, "value") else str(obj.type) for obj in obj_result.scalars().all()}
        
        for impact in request.objectiveImpacts:
            obj_type = objectives.get(impact.objectiveId)
            if obj_type == "health": behavior.impact_on_health = impact.impactScore
            elif obj_type == "productivity": behavior.impact_on_productivity = impact.impactScore
            elif obj_type == "learning": behavior.impact_on_learning = impact.impactScore
            elif obj_type == "wellness": behavior.impact_on_wellness = impact.impactScore
            elif obj_type == "social": behavior.impact_on_social = impact.impactScore

    await db.commit()
    await db.refresh(behavior)

    objective_map = await get_objective_map(db, current_user.id)
    return ApiResponse(
        data=map_behavior_to_response(behavior, objective_map=objective_map),
        message="Behavior updated successfully"
    ).dict(exclude_none=True)


@router.delete("/{behavior_id}", response_model=ApiResponse[dict])
async def delete_behavior(
    behavior_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
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

    return ApiResponse(
        success=True,
        message="Behavior deleted successfully",
        data={"id": str(behavior_id)}
    ).dict(exclude_none=True)
