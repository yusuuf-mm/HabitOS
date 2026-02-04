"""Analytics routes."""
import logging
from datetime import datetime, timezone, timedelta, date
from typing import List
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends

from app.api.deps import get_db, get_current_active_user
from app.models import (
    User, 
    Behavior, 
    CompletionLog, 
    OptimizationRun, 
    ScheduledBehavior,
    Objective,
    OptimizationStatus
)
from app.schemas.api import ApiResponse
from app.schemas.analytics import DashboardSummary, DashboardStats, AnalyticsData, BehaviorCompletion, ObjectiveProgress, CategoryDistribution, EnergyUsage, DashboardScheduledBehavior, DashboardBehavior
from app.schemas.optimization import OptimizationSummary, ScheduledBehaviorResponse
from app.api.v1.behaviors import map_behavior_to_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


async def calculate_streak(db: AsyncSession, user_id) -> int:
    """Calculate current streak of days with completed behaviors."""
    # Get all completion dates for the user, ordered by date descending
    result = await db.execute(
        select(func.date(CompletionLog.completed_at))
        .where(CompletionLog.user_id == user_id)
        .group_by(func.date(CompletionLog.completed_at))
        .order_by(func.date(CompletionLog.completed_at).desc())
    )
    completion_dates = [row[0] for row in result.all()]
    
    if not completion_dates:
        return 0
    
    # Check if there's activity today or yesterday
    today = date.today()
    yesterday = today - timedelta(days=1)
    
    if completion_dates[0] not in (today, yesterday):
        return 0
    
    # Count consecutive days
    streak = 1
    current_date = completion_dates[0]
    
    for completion_date in completion_dates[1:]:
        expected_prev_date = current_date - timedelta(days=1)
        if completion_date == expected_prev_date:
            streak += 1
            current_date = completion_date
        else:
            break
    
    return streak


@router.get("/summary", response_model=ApiResponse[DashboardSummary])
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ApiResponse[DashboardSummary]:
    """Get dashboard summary with real data."""
    # Total and active behaviors
    total_behaviors_result = await db.execute(
        select(func.count(Behavior.id)).where(Behavior.user_id == current_user.id)
    )
    total_behaviors = total_behaviors_result.scalar() or 0
    
    active_behaviors_result = await db.execute(
        select(func.count(Behavior.id)).where(
            and_(Behavior.user_id == current_user.id, Behavior.is_active == True)
        )
    )
    active_behaviors = active_behaviors_result.scalar() or 0
    
    # Total optimization runs
    total_runs_result = await db.execute(
        select(func.count(OptimizationRun.id)).where(OptimizationRun.user_id == current_user.id)
    )
    total_runs = total_runs_result.scalar() or 0
    
    # Completion rate (last 7 days)
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    scheduled_result = await db.execute(
        select(func.count(ScheduledBehavior.id))
        .join(OptimizationRun)
        .where(
            and_(
                OptimizationRun.user_id == current_user.id,
                OptimizationRun.created_at >= seven_days_ago
            )
        )
    )
    total_scheduled = scheduled_result.scalar() or 0
    
    completed_result = await db.execute(
        select(func.count(CompletionLog.id))
        .where(
            and_(
                CompletionLog.user_id == current_user.id,
                CompletionLog.completed_at >= seven_days_ago
            )
        )
    )
    total_completed = completed_result.scalar() or 0
    
    completion_rate = (total_completed / total_scheduled) if total_scheduled > 0 else 0.0
    
    # Average satisfaction score
    avg_score_result = await db.execute(
        select(func.avg(CompletionLog.satisfaction_score))
        .where(CompletionLog.user_id == current_user.id)
    )
    avg_score = avg_score_result.scalar() or 0.0
    avg_score_normalized = (float(avg_score) / 5.0) if avg_score > 0 else 0.0  # Normalize to 0-1
    
    # Streak days
    streak_days = await calculate_streak(db, current_user.id)
    
    # Recent optimizations (last 5)
    recent_opts_result = await db.execute(
        select(OptimizationRun)
        .where(OptimizationRun.user_id == current_user.id)
        .order_by(OptimizationRun.created_at.desc())
        .limit(5)
    )
    recent_opts = recent_opts_result.scalars().all()
    
    # Recent behaviors (most recently completed, last 5)
    recent_behaviors_result = await db.execute(
        select(Behavior, func.max(CompletionLog.completed_at))
        .join(CompletionLog, CompletionLog.behavior_id == Behavior.id)
        .where(Behavior.user_id == current_user.id)
        .group_by(Behavior.id)
        .order_by(func.max(CompletionLog.completed_at).desc())
        .limit(5)
    )
    recent_behaviors = [row[0] for row in recent_behaviors_result.all()]
    
    # Today's schedule
    today = date.today()
    today_schedule_result = await db.execute(
        select(ScheduledBehavior, Behavior)
        .join(Behavior, ScheduledBehavior.behavior_id == Behavior.id)
        .join(OptimizationRun, ScheduledBehavior.optimization_run_id == OptimizationRun.id)
        .where(
            and_(
                OptimizationRun.user_id == current_user.id,
                OptimizationRun.start_date == today,
                OptimizationRun.status == OptimizationStatus.COMPLETED
            )
        )
        .order_by(ScheduledBehavior.time_period)
    )
    today_schedule_raw = today_schedule_result.all()

    # Time mapping logic
    def period_to_time(p):
        total_mins = p * 15 # Assuming 15-min periods as per schedule.py
        h = (total_mins // 60) % 24
        m = total_mins % 60
        return f"{h:02d}:{m:02d}"

    # Check for completions
    completion_result = await db.execute(
        select(CompletionLog.behavior_id)
        .join(OptimizationRun, CompletionLog.optimization_run_id == OptimizationRun.id)
        .where(
            and_(
                CompletionLog.user_id == current_user.id,
                OptimizationRun.start_date == today
            )
        )
    )
    completed_behavior_ids = {row[0] for row in completion_result.all()}

    return ApiResponse(
        success=True,
        message="Summary retrieved",
        data=DashboardSummary(
            stats=DashboardStats(
                total_behaviors=total_behaviors,
                active_behaviors=active_behaviors,
                total_optimization_runs=total_runs,
                completion_rate=round(completion_rate, 2),
                average_score=round(avg_score_normalized, 2),
                streak_days=streak_days,
            ),
            recent_optimizations=[
                OptimizationSummary(
                    id=opt.id,
                    status=opt.status.value if hasattr(opt.status, 'value') else str(opt.status),
                    score=round(opt.total_objective_value or 0, 2),
                    created_at=opt.created_at
                )
                for opt in recent_opts
            ],
            recent_behaviors=[
                DashboardBehavior(
                    id=b.id,
                    name=b.name,
                    category=b.category.value if hasattr(b.category, 'value') else str(b.category),
                    is_active=b.is_active,
                    created_at=b.created_at
                )
                for b in recent_behaviors
            ],
            today_schedule=[
                DashboardScheduledBehavior(
                    id=sb.id,
                    behavior_name=b.name,
                    time_slot="flexible", # Default for dashboard
                    start_time=period_to_time(sb.time_period % 96), # Map to day's period
                    is_completed=sb.behavior_id in completed_behavior_ids
                )
                for sb, b in today_schedule_raw
            ],
        )
    )


@router.get("/stats", response_model=ApiResponse[DashboardStats])
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ApiResponse[DashboardStats]:
    """Get dashboard stats."""
    # Reuse same logic as summary
    summary_resp = await get_dashboard_summary(db, current_user)
    return ApiResponse(
        success=True,
        message="Stats retrieved",
        data=summary_resp.data.stats
    )


@router.get("", response_model=ApiResponse[AnalyticsData])
async def get_analytics(
    period: str = "7d",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ApiResponse[AnalyticsData]:
    """Get detailed analytics."""
    # Parse period
    days = 7
    if period.endswith("d"):
        try:
            days = int(period[:-1])
        except ValueError:
            days = 7
    
    start_date = date.today() - timedelta(days=days)
    
    # Behavior completions by date
    completions_result = await db.execute(
        select(
            func.date(CompletionLog.completed_at).label("date"),
            func.count(CompletionLog.id).label("completed")
        )
        .where(
            and_(
                CompletionLog.user_id == current_user.id,
                func.date(CompletionLog.completed_at) >= start_date
            )
        )
        .group_by(func.date(CompletionLog.completed_at))
        .order_by(func.date(CompletionLog.completed_at))
    )
    completions = completions_result.all()
    
    # Get scheduled counts by date
    scheduled_result = await db.execute(
        select(
            OptimizationRun.start_date.label("date"),
            func.count(ScheduledBehavior.id).label("scheduled")
        )
        .join(ScheduledBehavior, ScheduledBehavior.optimization_run_id == OptimizationRun.id)
        .where(
            and_(
                OptimizationRun.user_id == current_user.id,
                OptimizationRun.start_date >= start_date
            )
        )
        .group_by(OptimizationRun.start_date)
        .order_by(OptimizationRun.start_date)
    )
    scheduled_counts = {row[0]: row[1] for row in scheduled_result.all()}
    
    behavior_completions = [
        BehaviorCompletion(
            date=row[0],
            completed=row[1],
            scheduled=scheduled_counts.get(row[0], 0),
        )
        for row in completions
    ]
    
    # Category distribution
    category_result = await db.execute(
        select(
            Behavior.category,
            func.count(Behavior.id).label("count")
        )
        .where(
            and_(
                Behavior.user_id == current_user.id,
                Behavior.is_active == True
            )
        )
        .group_by(Behavior.category)
    )
    categories = category_result.all()
    total_cat = sum(row[1] for row in categories)
    
    category_distribution = [
        CategoryDistribution(
            category=row[0].value if hasattr(row[0], 'value') else str(row[0]),
            count=row[1],
            percentage=round((row[1] / total_cat * 100) if total_cat > 0 else 0, 1),
        )
        for row in categories
    ]
    
    # Objective progress (simplified - showing average impact scores)
    objectives_result = await db.execute(
        select(Objective).where(Objective.user_id == current_user.id)
    )
    objectives = objectives_result.scalars().all()
    
    objective_progress = []
    for obj in objectives:
        obj_name = obj.type.value if hasattr(obj.type, 'value') else str(obj.type)
        objective_progress.append(ObjectiveProgress(
            objective_name=obj_name.capitalize(),
            progress=round(obj.weight * 100, 1),
            trend="stable",
        ))
    
    # Energy usage (mock for now)
    energy_usage = [
        EnergyUsage(
            date=start_date + timedelta(days=i),
            energy_spent=0,
            energy_budget=100,
        )
        for i in range(days)
    ]
    
    return ApiResponse(
        success=True,
        message="Analytics retrieved",
        data=AnalyticsData(
            period=period,
            behavior_completions=behavior_completions,
            objective_progress=objective_progress,
            category_distribution=category_distribution,
            energy_usage=energy_usage,
        )
    )
