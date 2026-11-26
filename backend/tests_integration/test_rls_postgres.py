"""RLS is on for every public table, with no policies and owner bypass intact.

Requires a real Postgres that has already been migrated with ``alembic upgrade
head``. Skipped when no Postgres URL is configured.

    TEST_POSTGRES_URL=postgresql+asyncpg://user:password@localhost:5432/db \
      uv run pytest tests_integration/test_rls_postgres.py -v
"""
import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

PG_URL = os.getenv("TEST_POSTGRES_URL") or os.getenv("DATABASE_URL") or ""
IS_POSTGRES = PG_URL.startswith("postgresql")

pytestmark = pytest.mark.skipif(
    not IS_POSTGRES,
    reason="needs a migrated real Postgres in TEST_POSTGRES_URL",
)

EXPECTED_TABLES = {
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
}


@pytest_asyncio.fixture
async def pg_engine():
    engine = create_async_engine(PG_URL, poolclass=NullPool)
    yield engine
    await engine.dispose()


async def test_every_public_table_has_rls_and_no_policies(pg_engine):
    async with pg_engine.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    "select c.relname as table_name, "
                    "c.relrowsecurity as row_security, "
                    "c.relforcerowsecurity as force_row_security "
                    "from pg_class c "
                    "join pg_namespace n on n.oid = c.relnamespace "
                    "where n.nspname = 'public' and c.relkind = 'r' "
                    "order by c.relname"
                )
            )
        ).mappings().all()
        policy_count = int(
            (
                await connection.execute(
                    text("select count(*) from pg_policies where schemaname = 'public'")
                )
            ).scalar_one()
        )

    by_table = {row["table_name"]: row for row in rows}
    assert EXPECTED_TABLES <= set(by_table), set(by_table)
    assert [name for name, row in by_table.items() if not row["row_security"]] == []
    assert [name for name, row in by_table.items() if row["force_row_security"]] == []
    assert policy_count == 0


async def test_owner_connection_still_reads_and_writes(pg_engine):
    user_id = uuid.uuid4()
    email = f"rls-probe-{user_id.hex[:12]}@example.com"
    try:
        async with pg_engine.begin() as connection:
            await connection.execute(
                text(
                    "insert into users "
                    "(id, email, username, password_hash, status, created_at, updated_at, timezone) "
                    "values (:id, :email, :username, 'not-a-real-hash', 'active', now(), now(), 'UTC')"
                ),
                {"id": str(user_id), "email": email, "username": f"rls{user_id.hex[:10]}"},
            )

        async with pg_engine.connect() as connection:
            found = int(
                (
                    await connection.execute(
                        text("select count(*) from users where id = :id"),
                        {"id": str(user_id)},
                    )
                ).scalar_one()
            )
        assert found == 1
    finally:
        async with pg_engine.begin() as connection:
            await connection.execute(
                text("delete from users where id = :id"), {"id": str(user_id)}
            )
