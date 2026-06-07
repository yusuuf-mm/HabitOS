"""Behavior -> Objective impact association model.

This is the normalized replacement for the eight ``impact_on_*`` columns that
used to live directly on the ``behaviors`` table. Adding a ninth objective type
now means: a new enum value, a migration to add the new enum variant, and
nothing else. No new behavior columns, no new branches in the API layer.
"""
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.objective import ObjectiveType

if TYPE_CHECKING:
    from app.models.behavior import Behavior


class ObjectiveImpact(Base):
    """A single impact score for a behavior on a specific objective type.

    The composite primary key (behavior_id, objective_type) prevents duplicate
    rows for the same behavior/objective pair and lets the solver join
    ``behaviors`` with this table to compute per-objective impact vectors.
    """

    __tablename__ = "objective_impacts"

    behavior_id: Mapped[UUID] = mapped_column(
        ForeignKey("behaviors.id", ondelete="CASCADE"),
        primary_key=True,
    )
    objective_type: Mapped[ObjectiveType] = mapped_column(
        SQLEnum(ObjectiveType, name="objectivetype"),
        primary_key=True,
    )
    impact_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    behavior: Mapped["Behavior"] = relationship(back_populates="objective_impacts")

    __table_args__ = (
        CheckConstraint(
            "impact_score >= -1.0 AND impact_score <= 1.0",
            name="ck_objective_impacts_score_range",
        ),
        Index("idx_objective_impacts_type", "objective_type"),
    )
