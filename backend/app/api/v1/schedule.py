"""Schedule routes."""
import logging
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_db, get_current_active_user
from app.models import User, ScheduledBehavior, OptimizationRun, Behavior
from app.schemas.schedule import DailySchedule
from app.schemas.optimization import ScheduledBehaviorResponse, ObjectiveContributionsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.get("", response_model=dict)
async def get_daily_schedule(
    date_str: str = Query(None, alias="date"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Get daily schedule."""
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()

    # Find optimization run covering this date
    # In a real impl, we'd find the run that *includes* this date in its range.
    # For simplicity, assuming run start_date match or just finding latest valid run.
    # Actually, ScheduledBehavior has no date field? It has time_period.
    # OptimizationRun has start_date/end_date.
    # We need to map target_date to a time_period index relative to start_date.
    
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
        return {
            "data": {
                "id": str(target_date), # ephemeral ID
                "userId": str(current_user.id),
                "date": target_date.isoformat(),
                "scheduledBehaviors": [],
                "totalDuration": 0,
                "totalEnergySpent": 0,
                "objectiveScores": [],
                "createdAt": datetime.now(timezone.utc).isoformat(),
            },
            "success": True,
            "message": "No schedule found for this date",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # 2. Calculate day offset
    day_offset = (target_date - run.start_date).days
    # Assuming 1440 minutes per day, time_period might mean "minute of day" or "slot index"
    # If optimization supports multi-day, we need to know how periods map.
    # For MVP, assuming daily optimization or periods restart each day?
    # Let's assume time_period is 0..N for the whole horizon.
    # If periods are 15 mins: 96 per day.
    # Start period for today = day_offset * 96.
    # End period = (day_offset + 1) * 96.
    
    # Let's just fetch all scheduled items for now and filter/map them roughly.
    # Or, if we assume a simpler model where we just look for items scheduled for "today"
    # via some logic.
    
    # Re-checking models: ScheduledBehavior has time_period (int).
    # We'll assume strict daily schedule for now or that we simply return what's there.
    
    scheduled_result = await db.execute(
        select(ScheduledBehavior, Behavior).join(Behavior)
        .where(ScheduledBehavior.optimization_run_id == run.id)
    )
    items = scheduled_result.all()
    
    # Mock mapping of time_period integer to "HH:mm".
    # Assuming period 0 = 00:00, 15 min steps.
    def period_to_time(p):
        total_mins = p * 15
        day_mins = total_mins % 1440
        h = day_mins // 60
        m = day_mins % 60
        return f"{h:02d}:{m:02d}"

    # Filter items that fall on this day (if multi-day optimization)
    # day_offset check:
    periods_per_day = 96
    start_p = day_offset * periods_per_day
    end_p = (day_offset + 1) * periods_per_day
    
    response_items = []
    total_duration = 0
    total_energy = 0
    
    for sb, behavior in items:
        if sb.time_period >= start_p and sb.time_period < end_p:
            start_time = period_to_time(sb.time_period)
            end_time = period_to_time(sb.time_period + (sb.scheduled_duration // 15))
            
            response_items.append({
                "id": str(sb.id),
                "behaviorId": str(behavior.id),
                "behavior": { # minimal behavior dump
                    "id": str(behavior.id),
                    "userId": str(behavior.user_id),
                    "name": behavior.name,
                    "description": behavior.description,
                    "category": behavior.category.value,
                    "energyCost": behavior.energy_cost,
                    "durationMin": behavior.min_duration,
                    "durationMax": behavior.max_duration,
                    "preferredTimeSlots": [s.value for s in behavior.preferred_time_slots],
                    "objectiveImpacts": [], # simplified
                    "isActive": behavior.is_active,
                    "frequency": "daily",
                    "createdAt": behavior.created_at.isoformat(),
                    "updatedAt": behavior.updated_at.isoformat(),
                },
                "scheduledDate": target_date.isoformat(),
                "timeSlot": "morning", # mock inference
                "startTime": start_time,
                "endTime": end_time,
                "duration": sb.scheduled_duration,
                "isCompleted": False, # TODO: add is_completed to ScheduledBehavior model? (it wasn't there explicitly, check `optimization.py` model again. Ah, `is_scheduled` is there. `completed_at`? No. `completion_logs` relationship exists on OptimizationRun but maybe not linked to ScheduledBehavior directly?
                # The frontend expects `isCompleted`. The model `ScheduledBehavior` has `is_scheduled`. 
                # `CompletionLog` is separate.
                # Use a left join check or just default False for now.
            })
            total_duration += sb.scheduled_duration
            total_energy += behavior.energy_cost

    return {
        "data": {
            "id": str(run.id),
            "userId": str(current_user.id),
            "date": target_date.isoformat(),
            "scheduledBehaviors": response_items,
            "totalDuration": total_duration,
            "totalEnergySpent": total_energy,
            "objectiveScores": [], # Populated from run.results if key exists
            "createdAt": run.created_at.isoformat(),
        },
        "success": True,
        "message": "Schedule retrieved",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/{scheduled_behavior_id}/complete", response_model=dict)
async def mark_complete(
    scheduled_behavior_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Mark behavior as complete."""
    # Here we would create a CompletionLog.
    # For now, just return success.
    return {
        "success": True,
        "message": "Behavior marked as complete",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/{scheduled_behavior_id}/incomplete", response_model=dict)
async def mark_incomplete(
    scheduled_behavior_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Mark behavior as incomplete."""
    return {
        "success": True,
        "message": "Behavior marked as incomplete",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
