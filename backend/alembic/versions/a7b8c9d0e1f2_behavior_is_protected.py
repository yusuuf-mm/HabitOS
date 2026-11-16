"""behaviors.is_protected: a flag the planner tiers on

Revision ID: a7b8c9d0e1f2
Revises: b3c4d5e6f7a8
Create Date: 2026-11-16 01:00:00.000000

A protected habit is placed before flexible ones and is never dropped silently:
when it cannot fit, the solve reports a protected conflict instead of a plan.
The column is additive and defaults to false, so every existing row stays a
flexible habit.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "behaviors",
        sa.Column("is_protected", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("behaviors", "is_protected")
