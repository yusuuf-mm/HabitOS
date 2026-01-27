"""Completion tracking model."""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import String, DateTime, ForeignKey, JSON, Integer, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class CompletionLog(Base):
    """Completion log model for tracking behavior completions."""

    __tablename__ = "completion_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    behavior_id: Mapped[UUID] = mapped_column(ForeignKey("behaviors.id", ondelete="CASCADE"))
    optimization_run_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("optimization_runs.id", ondelete="SET NULL"), nullable=True
    )
    actual_duration: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    satisfaction_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="completion_logs")
    behavior: Mapped["Behavior"] = relationship(back_populates="completion_logs")
    optimization_run: Mapped[Optional["OptimizationRun"]] = relationship(back_populates="completion_logs")

    __table_args__ = (
        Index("idx_completion_logs_user_id", "user_id"),
        Index("idx_completion_logs_behavior_id", "behavior_id"),
        Index("idx_completion_logs_completed_at", "completed_at"),
        Index("idx_completion_logs_optimization_run_id", "optimization_run_id"),
    )
