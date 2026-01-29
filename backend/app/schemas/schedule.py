"""Schedule schemas."""
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel

from app.schemas.optimization import ScheduledBehaviorResponse, ObjectiveContributionsResponse


class DailySchedule(BaseModel):
    """Daily schedule schema."""

    id: UUID
    user_id: UUID
    date: date
    scheduled_behaviors: List[ScheduledBehaviorResponse]
    total_duration: int
    total_energy_spent: int
    objective_scores: List[ObjectiveContributionsResponse]
    created_at: datetime

    class Config:
        """Pydantic config."""

        from_attributes = True
