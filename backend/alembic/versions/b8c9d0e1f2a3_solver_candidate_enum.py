"""solvertype: record the candidate solver

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-11-16 01:10:00.000000

The runs table could only name the four original solver families, so every plan
recorded ``linear`` while diagnostics carried the truth. Adding the value makes
the column an honest record.

Postgres cannot drop an enum value, so the downgrade rebuilds the type: rows
using the new value are moved back to ``LINEAR`` first, then the column is cast
to a type that does not contain it.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORIGINAL_VALUES = ("LINEAR", "NONLINEAR", "HEURISTIC", "EVOLUTIONARY")


def upgrade() -> None:
    op.execute("ALTER TYPE solvertype ADD VALUE IF NOT EXISTS 'CANDIDATE'")


def downgrade() -> None:
    op.execute("UPDATE optimization_runs SET solver = 'LINEAR' WHERE solver = 'CANDIDATE'")
    op.execute("ALTER TYPE solvertype RENAME TO solvertype_old")
    values = ", ".join(f"'{value}'" for value in _ORIGINAL_VALUES)
    op.execute(f"CREATE TYPE solvertype AS ENUM ({values})")
    op.execute(
        "ALTER TABLE optimization_runs "
        "ALTER COLUMN solver TYPE solvertype USING solver::text::solvertype"
    )
    op.execute("DROP TYPE solvertype_old")
