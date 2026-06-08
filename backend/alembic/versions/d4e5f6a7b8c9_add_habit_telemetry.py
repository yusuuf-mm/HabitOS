"""Add habit_telemetry table for end-of-day aggregation.

Revision ID: d4e5f6a7b8c9
Revises: c1a2b3c4d5e6
Create Date: 2026-06-08
"""

from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "habit_telemetry",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("planned_impact", sa.Float(), nullable=False, server_default="0"),
        sa.Column("actual_impact", sa.Float(), nullable=False, server_default="0"),
        sa.Column("consistency_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_behaviors_planned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_behaviors_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_duration_planned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_duration_actual", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("objective_breakdown", sa.JSON(), nullable=True),
        sa.Column("behavior_breakdown", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_habit_telemetry_user_id", "habit_telemetry", ["user_id"])
    op.create_index("idx_habit_telemetry_snapshot_date", "habit_telemetry", ["snapshot_date"])
    op.create_index(
        "idx_habit_telemetry_user_date",
        "habit_telemetry",
        ["user_id", "snapshot_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_habit_telemetry_user_date")
    op.drop_index("idx_habit_telemetry_snapshot_date")
    op.drop_index("idx_habit_telemetry_user_id")
    op.drop_table("habit_telemetry")
