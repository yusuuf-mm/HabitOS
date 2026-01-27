"""Optimization models."""
from datetime import datetime, timezone, date
from enum import Enum
from typing import Optional, List
from uuid import UUID

from sqlalchemy import String, DateTime, ForeignKey, JSON, Float, Integer, Boolean, Date, Index, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class OptimizationStatus(str, Enum):
    """Optimization run status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SolverType(str, Enum):
    """Solver types."""

    LINEAR = "linear"
    NONLINEAR = "nonlinear"
    HEURISTIC = "heuristic"
    EVOLUTIONARY = "evolutionary"


class OptimizationRun(Base):
    """Optimization run model."""

    __tablename__ = "optimization_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[OptimizationStatus] = mapped_column(SQLEnum(OptimizationStatus), default=OptimizationStatus.PENDING)
    solver: Mapped[SolverType] = mapped_column(SQLEnum(SolverType))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    time_periods: Mapped[int] = mapped_column(Integer, nullable=False)
    results: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    diagnostics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    total_objective_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    execution_time_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="optimization_runs")
    scheduled_behaviors: Mapped[List["ScheduledBehavior"]] = relationship(
        back_populates="optimization_run", cascade="all, delete-orphan"
    )
    completion_logs: Mapped[List["CompletionLog"]] = relationship(back_populates="optimization_run")

    __table_args__ = (
        Index("idx_optimization_runs_user_id", "user_id"),
        Index("idx_optimization_runs_status", "status"),
        Index("idx_optimization_runs_created_at", "created_at"),
    )


class ScheduledBehavior(Base):
    """Scheduled behavior from optimization result."""

    __tablename__ = "scheduled_behaviors"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    optimization_run_id: Mapped[UUID] = mapped_column(ForeignKey("optimization_runs.id", ondelete="CASCADE"))
    behavior_id: Mapped[UUID] = mapped_column(ForeignKey("behaviors.id", ondelete="CASCADE"))
    time_period: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_duration: Mapped[int] = mapped_column(Integer, nullable=False)
    is_scheduled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    optimization_run: Mapped["OptimizationRun"] = relationship(back_populates="scheduled_behaviors")
    behavior: Mapped["Behavior"] = relationship(back_populates="scheduled_behaviors")

    __table_args__ = (
        Index("idx_scheduled_behaviors_optimization_run_id", "optimization_run_id"),
        Index("idx_scheduled_behaviors_behavior_id", "behavior_id"),
    )
