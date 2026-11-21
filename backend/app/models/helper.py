"""Helper confirmations: idempotency keys + transcript storage for the AI helper."""
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class HelperConfirmation(Base):
    """One confirmed helper draft.

    The transcript lives ONLY here: drafts never write, and items/behaviours
    carry no dictation text. The (user_id, draft_id) pair makes confirm
    idempotent: a retry returns the stored ids instead of duplicating rows.
    """

    __tablename__ = "helper_confirmations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    draft_id: Mapped[str] = mapped_column(String(64), nullable=False)
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    item_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    behavior_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "draft_id", name="uq_helper_confirmation_draft"
        ),
        Index("idx_helper_confirmations_user_id", "user_id"),
    )
