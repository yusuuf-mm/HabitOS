"""Schedule schemas."""
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.optimization import ScheduledBehaviorResponse, ObjectiveContributionSchema


class DailySchedule(BaseModel):
    """Daily schedule schema."""

    id: UUID
    userId: UUID = Field(..., alias="user_id")
    date: date
    scheduledBehaviors: List[ScheduledBehaviorResponse] = Field(..., alias="scheduled_behaviors")
    totalDuration: int = Field(..., alias="total_duration")
    totalEnergySpent: int = Field(..., alias="total_energy_spent")
    objectiveScores: List[ObjectiveContributionSchema] = Field(..., alias="objective_scores")
    createdAt: datetime = Field(..., alias="created_at")

    class Config:
        """Pydantic config."""

        from_attributes = True
        populate_by_name = True
