"""items table: commitments and deadlines.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-11-18 00:00:00.000000

One table with a ``kind`` column and nullable columns per kind, guarded by the
``ck_items_kind_fields`` CHECK constraint plus Pydantic validation at the edge.
Generic SQLAlchemy types only so the migration runs on Postgres and SQLite.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CK_ITEMS_KIND_FIELDS = (
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
    "recurrence_until IS NULL AND weekdays IS NULL))"
)


def upgrade() -> None:
    op.create_table(
        "items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "is_private",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("recurrence", sa.String(20), nullable=True),
        sa.Column("recurrence_until", sa.Date(), nullable=True),
        sa.Column("weekdays", sa.Integer(), nullable=True),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("prep_minutes", sa.Integer(), nullable=True),
        sa.Column("prep_lead_days", sa.Integer(), nullable=True),
        sa.Column("reminder_offsets", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(_CK_ITEMS_KIND_FIELDS, name="ck_items_kind_fields"),
    )
    op.create_index("idx_items_user_id", "items", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_items_user_id", table_name="items")
    op.drop_table("items")
