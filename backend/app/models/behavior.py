"""Behavior model."""
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, ForeignKey, Index, Enum as SQLEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ARRAY

from app.db.database import Base


class BehaviorCategory(str, Enum):
    """Behavior categories."""

    HEALTH = "health"
    PRODUCTIVITY = "productivity"
    LEARNING = "learning"
    WELLNESS = "wellness"
    SOCIAL = "social"
    FINANCIAL = "financial"
    CREATIVITY = "creativity"
    MINDFULNESS = "mindfulness"


class TimeSlot(str, Enum):
    """Preferred time slots for behaviors."""

    EARLY_MORNING = "early_morning"
    MORNING = "morning"
    MIDDAY = "midday"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"
    FLEXIBLE = "flexible"


class Behavior(Base):
    """Behavior model."""

    __tablename__ = "behaviors"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[BehaviorCategory] = mapped_column(SQLEnum(BehaviorCategory))
    min_duration: Mapped[int] = mapped_column(Integer, nullable=False)
    typical_duration: Mapped[int] = mapped_column(Integer, nullable=False)
    max_duration: Mapped[int] = mapped_column(Integer, nullable=False)
    energy_cost: Mapped[float] = mapped_column(Float, default=1.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    preferred_time_slots: Mapped[list[TimeSlot]] = mapped_column(
        ARRAY(SQLEnum(TimeSlot)).with_variant(JSON, "sqlite"), 
        default=[TimeSlot.FLEXIBLE]
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    # Impact on objectives (0-1 scale)
    impact_on_health: Mapped[float] = mapped_column(Float, default=0.0)
    impact_on_productivity: Mapped[float] = mapped_column(Float, default=0.0)
    impact_on_learning: Mapped[float] = mapped_column(Float, default=0.0)
    impact_on_wellness: Mapped[float] = mapped_column(Float, default=0.0)
    impact_on_social: Mapped[float] = mapped_column(Float, default=0.0)
    impact_on_financial: Mapped[float] = mapped_column(Float, default=0.0)
    impact_on_creativity: Mapped[float] = mapped_column(Float, default=0.0)
    impact_on_mindfulness: Mapped[float] = mapped_column(Float, default=0.0)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="behaviors")
    completion_logs: Mapped[List["CompletionLog"]] = relationship(back_populates="behavior", cascade="all, delete-orphan")
    scheduled_behaviors: Mapped[List["ScheduledBehavior"]] = relationship(back_populates="behavior", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_behaviors_user_id", "user_id"),
        Index("idx_behaviors_category", "category"),
        Index("idx_behaviors_is_active", "is_active"),
    )

    def get_impact(self, objective_type: str) -> float:
        """Get impact for specific objective type."""
        impacts = {
            "health": self.impact_on_health,
            "productivity": self.impact_on_productivity,
            "learning": self.impact_on_learning,
            "wellness": self.impact_on_wellness,
            "social": self.impact_on_social,
            "financial": self.impact_on_financial,
            "creativity": self.impact_on_creativity,
            "mindfulness": self.impact_on_mindfulness,
        }
        return impacts.get(objective_type, 0.0)

    def get_all_impacts(self) -> dict:
        """Get all impacts as dictionary."""
        return {
            "health": self.impact_on_health,
            "productivity": self.impact_on_productivity,
            "learning": self.impact_on_learning,
            "wellness": self.impact_on_wellness,
            "social": self.impact_on_social,
            "financial": self.impact_on_financial,
            "creativity": self.impact_on_creativity,
            "mindfulness": self.impact_on_mindfulness,
        }
