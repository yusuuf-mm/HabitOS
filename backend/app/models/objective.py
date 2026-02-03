"""Objective model."""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import String, Float, DateTime, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class ObjectiveType(str, Enum):
    """Objective types."""

    HEALTH = "health"
    PRODUCTIVITY = "productivity"
    LEARNING = "learning"
    WELLNESS = "wellness"
    SOCIAL = "social"
    FINANCIAL = "financial"
    CREATIVITY = "creativity"
    MINDFULNESS = "mindfulness"


class Objective(Base):
    """Objective model."""

    __tablename__ = "objectives"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[ObjectiveType] = mapped_column(SQLEnum(ObjectiveType))
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="objectives")

    __table_args__ = (
        Index("idx_objectives_user_id", "user_id"),
        Index("idx_objectives_type", "type"),
    )

    @classmethod
    def get_default_objectives(cls) -> dict:
        """Get default objectives with sensible weights."""
        total = 8  # Number of objective types
        weight = 1.0 / total
        return {
            ObjectiveType.HEALTH: weight,
            ObjectiveType.PRODUCTIVITY: weight,
            ObjectiveType.LEARNING: weight,
            ObjectiveType.WELLNESS: weight,
            ObjectiveType.SOCIAL: weight,
            ObjectiveType.FINANCIAL: weight,
            ObjectiveType.CREATIVITY: weight,
            ObjectiveType.MINDFULNESS: weight,
        }

    @staticmethod
    def validate_weights(weights: dict) -> bool:
        """Validate that weights sum to 1.0."""
        total = sum(weights.values())
        return abs(total - 1.0) < 0.01  # Allow small floating point errors
