"""soft delete behaviors and preserve history

Revision ID: e1f2a3b4c5d6
Revises: d4e5f6a7b8c9
Create Date: 2026-11-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _replace_behavior_fk(table: str, ondelete: str) -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table(table, recreate="always") as batch_op:
            batch_op.drop_constraint(f"fk_{table}_behavior_id_behaviors", type_="foreignkey")
            batch_op.create_foreign_key(
                f"fk_{table}_behavior_id_behaviors",
                "behaviors",
                ["behavior_id"],
                ["id"],
                ondelete=ondelete,
            )
        return

    # PostgreSQL / others: try common auto-generated name, then inspect.
    fk_name = f"{table}_behavior_id_fkey"
    try:
        op.drop_constraint(fk_name, table, type_="foreignkey")
    except Exception:
        insp = sa.inspect(bind)
        for fk in insp.get_foreign_keys(table):
            if fk.get("referred_table") == "behaviors" and fk.get("constrained_columns") == ["behavior_id"]:
                if fk.get("name"):
                    op.drop_constraint(fk["name"], table, type_="foreignkey")
                break
    op.create_foreign_key(
        fk_name,
        table,
        "behaviors",
        ["behavior_id"],
        ["id"],
        ondelete=ondelete,
    )


def upgrade() -> None:
    _replace_behavior_fk("scheduled_behaviors", "RESTRICT")
    _replace_behavior_fk("completion_logs", "RESTRICT")


def downgrade() -> None:
    _replace_behavior_fk("completion_logs", "CASCADE")
    _replace_behavior_fk("scheduled_behaviors", "CASCADE")
