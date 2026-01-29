"""Analytics routes."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_active_user
from app.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=dict)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Get dashboard summary."""
    # Mock data structure to satisfy frontend
    return {
        "data": {
            "stats": {
                "totalBehaviors": 5,
                "activeBehaviors": 3,
                "totalOptimizationRuns": 12,
                "completionRate": 0.75,
                "averageScore": 0.82,
                "streakDays": 4,
            },
            "recentOptimizations": [],
            "recentBehaviors": [],
            "todaySchedule": [],
        },
        "success": True,
        "message": "Summary retrieved",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/stats", response_model=dict)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Get dashboard stats."""
    return {
        "data": {
            "totalBehaviors": 5,
            "activeBehaviors": 3,
            "totalOptimizationRuns": 12,
            "completionRate": 0.75,
            "averageScore": 0.82,
            "streakDays": 4,
        },
        "success": True,
        "message": "Stats retrieved",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("", response_model=dict)
async def get_analytics(
    period: str = "7d",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Get detailed analytics."""
    return {
        "data": {
            "period": period,
            "behaviorCompletions": [],
            "objectiveProgress": [],
            "categoryDistribution": [],
            "energyUsage": [],
        },
        "success": True,
        "message": "Analytics retrieved",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
