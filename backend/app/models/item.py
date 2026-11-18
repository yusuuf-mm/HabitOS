"""Item model: commitments and deadlines (no habit kind in part A)."""
from datetime import datetime, timezone, date, time
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    String,
    Text,
    Integer,
    Boolean,
    DateTime,
    Date,
    Time,
    ForeignKey,
    Index,
    JSON,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Item(Base):
    """A commitment (fixed start + duration) or a deadline (a date)."""

    __tablename__ = "items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Commitment fields (nullable; required by CHECK when kind='commitment').
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    start_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    timezone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recurrence: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    recurrence_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # Bitmask Mon=1, Tue=2, Wed=4, Thu=8, Fri=16, Sat=32, Sun=64.
    weekdays: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Deadline fields (nullable).
    due_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    prep_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    prep_lead_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reminder_offsets: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_items_user_id", "user_id"),
        CheckConstraint(
            "(kind IN ('commitment', 'deadline')) AND "
            "((kind <> 'commitment') OR "
            "(start_date IS NOT NULL AND start_time IS NOT NULL AND "
            "timezone IS NOT NULL AND duration_minutes IS NOT NULL AND "
            "recurrence IS NOT NULL AND "
            "due_on IS NULL AND prep_minutes IS NULL AND "
            "reminder_offsets IS NULL)) AND "
            "((kind <> 'deadline') OR "
            "(due_on IS NOT NULL AND "
            "start_date IS NULL AND start_time IS NULL AND timezone IS NULL AND "
            "duration_minutes IS NULL AND recurrence IS NULL AND "
            "recurrence_until IS NULL AND weekdays IS NULL))",
            name="ck_items_kind_fields",
        ),
    )
