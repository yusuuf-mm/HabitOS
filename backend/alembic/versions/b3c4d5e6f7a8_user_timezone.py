"""user timezone for plan-local day boundaries

Revision ID: b3c4d5e6f7a8
Revises: f2a3b4c5d6e7
Create Date: 2026-11-14 09:00:00.000000

docs/METRIC.md §5: the metric needs a per-user IANA timezone for the day boundary,
the 05:00 baseline hour and current-period checks. Existing users default to UTC,
which is what every boundary calculation used before this column existed.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC")
        )

    # A session that survives a re-plan keeps its id, so the id repeats once per
    # revision. The old global uniqueness made carrying a session forward
    # impossible, and the completion FK pointed at that uniqueness.
    if not is_sqlite:
        op.drop_constraint(
            "fk_completion_logs_planned_session_id", "completion_logs", type_="foreignkey"
        )
    op.drop_constraint(
        "uq_scheduled_behaviors_planned_session_id",
        "scheduled_behaviors",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_scheduled_behaviors_session_revision",
        "scheduled_behaviors",
        ["planned_session_id", "optimization_run_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    op.drop_constraint(
        "uq_scheduled_behaviors_session_revision",
        "scheduled_behaviors",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_scheduled_behaviors_planned_session_id",
        "scheduled_behaviors",
        ["planned_session_id"],
    )
    if not is_sqlite:
        op.create_foreign_key(
            "fk_completion_logs_planned_session_id",
            "completion_logs",
            "scheduled_behaviors",
            ["planned_session_id"],
            ["planned_session_id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("users") as batch:
        batch.drop_column("timezone")
