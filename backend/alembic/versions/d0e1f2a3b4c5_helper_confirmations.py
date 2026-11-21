"""helper_confirmations table: confirm idempotency + transcript storage.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-11-21 00:00:00.000000

One row per confirmed helper draft. The (user_id, draft_id) pair makes
confirm idempotent: a retry returns the stored ids instead of duplicating
rows. The transcript lives ONLY here: drafts never write, and items /
behaviours carry no dictation text.
Generic SQLAlchemy types only so the migration runs on Postgres and SQLite.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "helper_confirmations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("draft_id", sa.String(64), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("item_ids", sa.JSON(), nullable=False),
        sa.Column("behavior_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id", "draft_id", name="uq_helper_confirmation_draft"
        ),
    )
    op.create_index(
        "idx_helper_confirmations_user_id", "helper_confirmations", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "idx_helper_confirmations_user_id", table_name="helper_confirmations"
    )
    op.drop_table("helper_confirmations")
