"""Schedule schemas."""
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.optimization import ScheduledBehaviorResponse, ObjectiveContributionSchema


class DailySchedule(BaseModel):
    """Daily schedule schema."""

    id: UUID
    userId: UUID = Field(..., validation_alias="user_id", serialization_alias="userId")
    date: date
    scheduledBehaviors: List[ScheduledBehaviorResponse] = Field(..., validation_alias="scheduled_behaviors", serialization_alias="scheduledBehaviors")
    totalDuration: int = Field(..., validation_alias="total_duration", serialization_alias="totalDuration")
    totalEnergySpent: int = Field(..., validation_alias="total_energy_spent", serialization_alias="totalEnergySpent")
    objectiveScores: List[ObjectiveContributionSchema] = Field(..., validation_alias="objective_scores", serialization_alias="objectiveScores")
    createdAt: datetime = Field(..., validation_alias="created_at", serialization_alias="createdAt")

    class Config:
        """Pydantic config."""

        from_attributes = True
        populate_by_name = True
