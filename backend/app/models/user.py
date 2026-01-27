"""User model."""
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from sqlalchemy import String, Boolean, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class User(Base):
    """User model."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_login: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    behaviors: Mapped[List["Behavior"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    objectives: Mapped[List["Objective"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    constraints: Mapped[List["Constraint"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    optimization_runs: Mapped[List["OptimizationRun"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    completion_logs: Mapped[List["CompletionLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_username", "username"),
    )
