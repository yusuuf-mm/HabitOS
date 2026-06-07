"""normalize behavior impacts

Revision ID: c1a2b3c4d5e6
Revises: b96cd1f49448
Create Date: 2026-06-07 16:20:00.000000

Replaces the eight ``impact_on_*`` columns on the ``behaviors`` table with a
normalized ``objective_impacts`` association table containing one row per
(behavior, objective_type) pair. The migration is a two-step process:

1. Create the new ``objective_impacts`` table.
2. Backfill from the legacy columns.
3. Drop the legacy columns.

The down-migration recreates the legacy columns and copies data back. The
backfill is best-effort: a column that was 0.0 is dropped from the new table
on the way back up, and rows that don't match the eight legacy enums are
ignored (in practice every impact does match one of them today).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c1a2b3c4d5e6"
down_revision: Union[str, None] = "b96cd1f49448"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Map each ObjectiveType enum value to the legacy column name on behaviors.
LEGACY_COLUMNS = (
    ("health", "impact_on_health"),
    ("productivity", "impact_on_productivity"),
    ("learning", "impact_on_learning"),
    ("wellness", "impact_on_wellness"),
    ("social", "impact_on_social"),
    ("financial", "impact_on_financial"),
    ("creativity", "impact_on_creativity"),
    ("mindfulness", "impact_on_mindfulness"),
)


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    is_postgres = bind.dialect.name == "postgresql"

    # SQLite + Postgres both support CREATE TABLE, but the enum column syntax
    # differs. Postgres can use a real ENUM type; SQLite gets a VARCHAR with a
    # CHECK constraint.
    if is_postgres:
        objective_type_enum = postgresql.ENUM(
            "HEALTH", "PRODUCTIVITY", "LEARNING", "WELLNESS",
            "SOCIAL", "FINANCIAL", "CREATIVITY", "MINDFULNESS",
            name="objectivetype",
            create_type=False,  # already exists from the initial migration
        )
        behavior_id_col = sa.Column(
            "behavior_id", sa.Uuid(),
            sa.ForeignKey("behaviors.id", ondelete="CASCADE"),
            primary_key=True,
        )
        objective_type_col = sa.Column(
            "objective_type", objective_type_enum, primary_key=True,
        )
    else:
        behavior_id_col = sa.Column(
            "behavior_id", sa.String(36),
            sa.ForeignKey("behaviors.id", ondelete="CASCADE"),
            primary_key=True,
        )
        objective_type_col = sa.Column(
            "objective_type", sa.String(20), primary_key=True,
        )

    op.create_table(
        "objective_impacts",
        behavior_id_col,
        objective_type_col,
        sa.Column("impact_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.CheckConstraint(
            "impact_score >= -1.0 AND impact_score <= 1.0",
            name="ck_objective_impacts_score_range",
        ),
    )
    op.create_index(
        "idx_objective_impacts_type", "objective_impacts", ["objective_type"]
    )

    # 2. Backfill from legacy columns. We only insert non-zero scores so a row
    # in the new table means "this behavior meaningfully affects that
    # objective", matching the original mapper's ``impact_score != 0`` filter.
    for enum_value, col in LEGACY_COLUMNS:
        if is_sqlite:
            op.execute(
                sa.text(
                    f"INSERT INTO objective_impacts (behavior_id, objective_type, impact_score) "
                    f"SELECT id, '{enum_value}', {col} FROM behaviors WHERE {col} != 0"
                )
            )
        else:
            # Cast the enum text into the existing objectivetype enum.
            op.execute(
                sa.text(
                    f"INSERT INTO objective_impacts (behavior_id, objective_type, impact_score) "
                    f"SELECT id, '{enum_value}'::objectivetype, {col} FROM behaviors WHERE {col} != 0"
                )
            )

    # 3. Drop the legacy columns.
    with op.batch_alter_table("behaviors") as batch_op:
        for _, col in LEGACY_COLUMNS:
            batch_op.drop_column(col)


def downgrade() -> None:
    bind = op.get_bind()

    # 1. Re-add the legacy columns as nullable; default 0; we fill them in below.
    with op.batch_alter_table("behaviors") as batch_op:
        for _, col in LEGACY_COLUMNS:
            batch_op.add_column(
                sa.Column(col, sa.Float(), nullable=False, server_default="0")
            )

    # 2. Copy data back from the new normalized table.
    for enum_value, col in LEGACY_COLUMNS:
        if bind.dialect.name == "sqlite":
            op.execute(
                sa.text(
                    f"UPDATE behaviors SET {col} = COALESCE("
                    f"(SELECT impact_score FROM objective_impacts "
                    f"WHERE objective_impacts.behavior_id = behaviors.id "
                    f"AND objective_type = '{enum_value}'), 0)"
                )
            )
        else:
            op.execute(
                sa.text(
                    f"UPDATE behaviors SET {col} = COALESCE("
                    f"(SELECT impact_score FROM objective_impacts "
                    f"WHERE objective_impacts.behavior_id = behaviors.id "
                    f"AND objective_type = '{enum_value}'), 0)"
                )
            )

    # 3. Drop the normalized table.
    op.drop_index("idx_objective_impacts_type", table_name="objective_impacts")
    op.drop_table("objective_impacts")
