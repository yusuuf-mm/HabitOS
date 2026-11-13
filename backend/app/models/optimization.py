"""Optimization models."""
from datetime import datetime, timezone, date
from enum import Enum
from typing import Optional, List
from uuid import UUID, uuid4

from sqlalchemy import String, DateTime, ForeignKey, JSON, Float, Integer, Boolean, Date, Index, UniqueConstraint, Uuid, Enum as SQLEnum, text
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

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
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
    # Metric bookkeeping (docs/METRIC.md §2): which revision of the day this is,
    # when the user accepted one, and which revision the day's baseline came from.
    plan_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    committed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    baseline_revision: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
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
        # Declared as a descending expression so the model matches the index the
        # migration creates (and what Postgres reflects back).
        Index("idx_optimization_runs_created_at", text("created_at DESC")),
    )


class ScheduledBehavior(Base):
    """Scheduled behavior from optimization result."""

    __tablename__ = "scheduled_behaviors"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    optimization_run_id: Mapped[UUID] = mapped_column(ForeignKey("optimization_runs.id", ondelete="CASCADE"))
    behavior_id: Mapped[UUID] = mapped_column(ForeignKey("behaviors.id", ondelete="RESTRICT"))
    time_period: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_duration: Mapped[int] = mapped_column(Integer, nullable=False)
    is_scheduled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Stable session identity: survives re-plans and binds completion logs, so the
    # metric counts sessions rather than behaviours (docs/METRIC.md §1).
    planned_session_id: Mapped[UUID] = mapped_column(
        Uuid, nullable=False, default=uuid4
    )
    plan_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    # Set when a later revision drops the session; the row is kept so a system
    # drop stays in the denominator. released_at covers a user release instead.
    retired_revision: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    released_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    optimization_run: Mapped["OptimizationRun"] = relationship(back_populates="scheduled_behaviors")
    behavior: Mapped["Behavior"] = relationship(back_populates="scheduled_behaviors")

    __table_args__ = (
        Index("idx_scheduled_behaviors_optimization_run_id", "optimization_run_id"),
        Index("idx_scheduled_behaviors_behavior_id", "behavior_id"),
        UniqueConstraint(
            "planned_session_id", name="uq_scheduled_behaviors_planned_session_id"
        ),
    )
