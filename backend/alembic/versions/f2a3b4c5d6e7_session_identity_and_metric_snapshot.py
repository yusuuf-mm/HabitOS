"""session identity and metric snapshot columns

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-11-13 12:00:00.000000

See docs/SESSION_SCHEMA.md. Additive: sessions gain a stable id, the revision
that produced them, and the two facts that classify them for the metric. Existing
rows are backfilled rather than dropped, and the downgrade removes only what this
revision added.
"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _backfill_session_ids() -> None:
    """Give every existing session a stable id."""
    bind = op.get_bind()

    sessions = sa.table(
        "scheduled_behaviors",
        sa.column("id", sa.Uuid()),
        sa.column("planned_session_id", sa.Uuid()),
        sa.column("optimization_run_id", sa.Uuid()),
        sa.column("behavior_id", sa.Uuid()),
        sa.column("time_period", sa.Integer()),
    )
    for (session_id,) in bind.execute(sa.select(sessions.c.id)).fetchall():
        bind.execute(
            sessions.update()
            .where(sessions.c.id == session_id)
            .values(planned_session_id=uuid.uuid4())
        )

    return


def _backfill_completion_links() -> None:
    """Point existing completions at the session they most likely completed."""
    bind = op.get_bind()
    sessions = sa.table(
        "scheduled_behaviors",
        sa.column("planned_session_id", sa.Uuid()),
        sa.column("optimization_run_id", sa.Uuid()),
        sa.column("behavior_id", sa.Uuid()),
        sa.column("time_period", sa.Integer()),
    )

    # One completion per (run, behaviour) can be matched: the earliest session of
    # that behaviour in the run. Everything else stays NULL rather than being
    # pointed at a session it may not have completed.
    logs = sa.table(
        "completion_logs",
        sa.column("id", sa.Uuid()),
        sa.column("behavior_id", sa.Uuid()),
        sa.column("optimization_run_id", sa.Uuid()),
        sa.column("planned_session_id", sa.Uuid()),
    )
    rows = bind.execute(
        sa.select(logs.c.id, logs.c.behavior_id, logs.c.optimization_run_id)
        .where(logs.c.optimization_run_id.is_not(None))
        .order_by(logs.c.id)
    ).fetchall()

    matched: dict[tuple[uuid.UUID, uuid.UUID], bool] = {}
    for log_id, behavior_id, run_id in rows:
        key = (behavior_id, run_id)
        if key in matched:
            continue
        session_id = bind.execute(
            sa.select(sessions.c.planned_session_id)
            .where(
                sa.and_(
                    sessions.c.optimization_run_id == run_id,
                    sessions.c.behavior_id == behavior_id,
                )
            )
            .order_by(sessions.c.time_period)
            .limit(1)
        ).scalar_one_or_none()
        if session_id is None:
            continue
        matched[key] = True
        bind.execute(
            logs.update()
            .where(logs.c.id == log_id)
            .values(planned_session_id=session_id)
        )


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    with op.batch_alter_table("optimization_runs") as batch:
        batch.add_column(
            sa.Column("plan_revision", sa.Integer(), nullable=False, server_default="1")
        )
        batch.add_column(
            sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("baseline_revision", sa.Integer(), nullable=True))

    with op.batch_alter_table("scheduled_behaviors") as batch:
        batch.add_column(sa.Column("planned_session_id", sa.Uuid(), nullable=True))
        batch.add_column(
            sa.Column("plan_revision", sa.Integer(), nullable=False, server_default="1")
        )
        batch.add_column(sa.Column("retired_revision", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("released_at", sa.DateTime(timezone=True), nullable=True)
        )

    _backfill_session_ids()

    if not is_sqlite:
        # SQLite leaves the column nullable: alembic's batch rebuild cannot put a
        # NOT NULL column behind a unique constraint there, and nothing running on
        # SQLite relies on it (tests build the schema from the models).
        op.alter_column(
            "scheduled_behaviors",
            "planned_session_id",
            existing_type=sa.Uuid(),
            nullable=False,
        )

    op.create_unique_constraint(
        "uq_scheduled_behaviors_planned_session_id",
        "scheduled_behaviors",
        ["planned_session_id"],
    )

    with op.batch_alter_table("completion_logs") as batch:
        batch.add_column(sa.Column("planned_session_id", sa.Uuid(), nullable=True))
    _backfill_completion_links()
    op.create_index(
        "idx_completion_logs_planned_session_id",
        "completion_logs",
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


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if not is_sqlite:
        op.drop_constraint(
            "fk_completion_logs_planned_session_id", "completion_logs", type_="foreignkey"
        )
    op.drop_index("idx_completion_logs_planned_session_id", table_name="completion_logs")
    with op.batch_alter_table("completion_logs") as batch:
        batch.drop_column("planned_session_id")

    op.drop_constraint(
        "uq_scheduled_behaviors_planned_session_id",
        "scheduled_behaviors",
        type_="unique",
    )
    with op.batch_alter_table("scheduled_behaviors") as batch:
        batch.drop_column("released_at")
        batch.drop_column("retired_revision")
        batch.drop_column("plan_revision")
        batch.drop_column("planned_session_id")

    with op.batch_alter_table("optimization_runs") as batch:
        batch.drop_column("baseline_revision")
        batch.drop_column("committed_at")
        batch.drop_column("plan_revision")
