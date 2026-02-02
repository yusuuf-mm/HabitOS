"""Constraint model."""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import String, DateTime, ForeignKey, JSON, Boolean, Index, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class ConstraintType(str, Enum):
    """Constraint types."""

    TIME_BUDGET = "time_budget"
    FREQUENCY = "frequency"
    DURATION_BOUNDS = "duration_bounds"
    PRECEDENCE = "precedence"
    MUTUAL_EXCLUSION = "mutual_exclusion"


class Constraint(Base):
    """Constraint model."""

    __tablename__ = "constraints"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[ConstraintType] = mapped_column(SQLEnum(ConstraintType))
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="constraints")

    __table_args__ = (
        Index("idx_constraints_user_id", "user_id"),
        Index("idx_constraints_type", "type"),
    )
