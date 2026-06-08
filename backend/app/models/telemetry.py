"""End-of-day telemetry aggregation model."""
from datetime import datetime, timezone, date
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    String, DateTime, ForeignKey, JSON, Float, Integer, Date, Index, Text
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class HabitTelemetry(Base):
    """Per-day aggregated telemetry record.

    Populated by the daily aggregation endpoint at the end of each day.
    Stores planned vs. actual impact, consistency score, and raw
    breakdowns so the frontend can render a 7-day trend card.
    """

    __tablename__ = "habit_telemetry"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)

    # High-level metrics
    planned_impact: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    actual_impact: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    consistency_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Counters
    total_behaviors_planned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_behaviors_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_duration_planned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_duration_actual: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Per-objective breakdown (JSON)
    objective_breakdown: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Per-behavior breakdown (JSON)
    behavior_breakdown: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_habit_telemetry_user_id", "user_id"),
        Index("idx_habit_telemetry_snapshot_date", "snapshot_date"),
        Index(
            "idx_habit_telemetry_user_date",
            "user_id",
            "snapshot_date",
            unique=True,
        ),
    )
