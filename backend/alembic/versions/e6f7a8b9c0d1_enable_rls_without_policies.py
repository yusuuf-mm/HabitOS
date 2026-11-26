"""enable RLS on every public table with no policies

Revision ID: e6f7a8b9c0d1
Revises: d0e1f2a3b4c5
Create Date: 2026-11-26

HabitOS keeps its own JWT auth. Supabase Auth is not introduced here, so there
are deliberately no policies: the anon key gets no rows through PostgREST while
the application's owner connection still bypasses RLS. FORCE ROW LEVEL SECURITY
is intentionally not set.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables present at this revision. Downgrade runs after later revisions have
# already dropped any tables added after this one.
PUBLIC_TABLES = (
    "alembic_version",
    "behaviors",
    "completion_logs",
    "constraints",
    "habit_telemetry",
    "helper_confirmations",
    "items",
    "objective_impacts",
    "objectives",
    "optimization_runs",
    "scheduled_behaviors",
    "users",
)


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _public_tables(bind) -> list[str]:
    return list(
        bind.execute(
            sa.text(
                "select tablename from pg_tables "
                "where schemaname = 'public' order by tablename"
            )
        ).scalars()
    )


def _public_policy_count(bind) -> int:
    return int(
        bind.execute(
            sa.text("select count(*) from pg_policies where schemaname = 'public'")
        ).scalar_one()
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite has no RLS; tests build their schema from the models.
        return

    if _public_policy_count(bind):
        raise RuntimeError(
            "Refusing to enable RLS while public policies exist; "
            "review them before this migration so nothing is silently dropped."
        )

    for table in _public_tables(bind):
        op.execute(
            f"ALTER TABLE public.{_quote_identifier(table)} ENABLE ROW LEVEL SECURITY"
        )

    if _public_policy_count(bind):
        raise RuntimeError("Unexpected public policy found after enabling RLS")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for table in PUBLIC_TABLES:
        op.execute(
            f"ALTER TABLE public.{_quote_identifier(table)} DISABLE ROW LEVEL SECURITY"
        )
