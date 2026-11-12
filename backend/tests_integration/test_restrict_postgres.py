"""RESTRICT foreign keys must be enforced by a real Postgres.

Skipped unless ``TEST_POSTGRES_URL`` (or ``DATABASE_URL``) points at Postgres, so
the default SQLite suite is unaffected. Point it at a disposable database: the
test creates its own rows and removes them again.

    TEST_POSTGRES_URL=postgresql+asyncpg://user:password@localhost:55433/behaviordb \
      uv run pytest tests_integration/test_restrict_postgres.py -v
"""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.models  # noqa: F401  (register all mappers)
from app.db.database import Base
from app.models import (
    Behavior,
    BehaviorCategory,
    CompletionLog,
    Objective,
    ObjectiveType,
    OptimizationRun,
    OptimizationStatus,
    ScheduledBehavior,
    SolverType,
    TimeSlot,
    User,
)

PG_URL = os.getenv("TEST_POSTGRES_URL") or os.getenv("DATABASE_URL") or ""
IS_POSTGRES = PG_URL.startswith("postgresql")

pytestmark = pytest.mark.skipif(
    not IS_POSTGRES,
    reason="needs a real Postgres URL in TEST_POSTGRES_URL (SQLite does not enforce this the same way)",
)


@pytest_asyncio.fixture
async def pg_engine():
    engine = create_async_engine(PG_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


async def test_hard_delete_of_behaviour_is_rejected_by_restrict(pg_engine):
    session_factory = async_sessionmaker(pg_engine, expire_on_commit=False)
    tag = uuid.uuid4().hex[:8]
    user_id = uuid.uuid4()
    behavior_id = uuid.uuid4()
    run_id = uuid.uuid4()

    try:
        async with session_factory() as session:
            session.add(
                User(
                    id=user_id,
                    email=f"restrict-{tag}@example.com",
                    username=f"restrict{tag}",
                    password_hash="not-a-real-hash",
                    status="active",
                )
            )
            await session.flush()
            session.add(
                Behavior(
                    id=behavior_id,
                    user_id=user_id,
                    name=f"RESTRICT probe {tag}",
                    category=BehaviorCategory.HEALTH,
                    min_duration=15,
                    typical_duration=30,
                    max_duration=45,
                    energy_cost=2.0,
                    is_active=True,
                    preferred_time_slots=[TimeSlot.MORNING],
                )
            )
            session.add(
                OptimizationRun(
                    id=run_id,
                    user_id=user_id,
                    status=OptimizationStatus.COMPLETED,
                    solver=SolverType.LINEAR,
                    start_date=date.today(),
                    end_date=date.today(),
                    time_periods=96,
                )
            )
            await session.flush()
            session.add(
                ScheduledBehavior(
                    optimization_run_id=run_id,
                    behavior_id=behavior_id,
                    time_period=32,
                    scheduled_duration=30,
                    is_scheduled=True,
                )
            )
            session.add(
                CompletionLog(
                    user_id=user_id,
                    behavior_id=behavior_id,
                    optimization_run_id=run_id,
                    actual_duration=30,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

        # 1. The constraints the test relies on must actually be RESTRICT.
        async with pg_engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "select conrelid::regclass::text, confdeltype::text "
                    "from pg_constraint where contype = 'f' and confrelid = 'behaviors'::regclass"
                )
            )
            delete_rules = dict(rows.all())
        assert delete_rules.get("scheduled_behaviors") == "r", delete_rules
        assert delete_rules.get("completion_logs") == "r", delete_rules

        # 2. A raw hard delete of the behaviour must be rejected by the database.
        with pytest.raises(IntegrityError) as exc_info:
            async with pg_engine.begin() as conn:
                await conn.execute(
                    text("delete from behaviors where id = :behavior_id"),
                    {"behavior_id": str(behavior_id)},
                )
        message = str(exc_info.value)
        assert "violates foreign key constraint" in message, message
        assert "scheduled_behaviors" in message or "completion_logs" in message, message

        # 3. The ORM path is rejected too, and nothing was removed.
        async with session_factory() as session:
            behavior = await session.get(Behavior, behavior_id)
            assert behavior is not None
            await session.delete(behavior)
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()

        async with session_factory() as session:
            still_there = await session.execute(
                select(Behavior.id).where(Behavior.id == behavior_id)
            )
            assert still_there.scalar() == behavior_id

        # 4. Removing the dependants first lets the behaviour go (RESTRICT, not NO ACTION deadlock).
        async with session_factory() as session:
            await session.execute(
                text("delete from completion_logs where behavior_id = :behavior_id"),
                {"behavior_id": str(behavior_id)},
            )
            await session.execute(
                text("delete from scheduled_behaviors where behavior_id = :behavior_id"),
                {"behavior_id": str(behavior_id)},
            )
            await session.commit()
        async with session_factory() as session:
            behavior = await session.get(Behavior, behavior_id)
            await session.delete(behavior)
            await session.commit()
        async with session_factory() as session:
            gone = await session.execute(select(Behavior.id).where(Behavior.id == behavior_id))
            assert gone.scalar() is None
    finally:
        # Best-effort cleanup of everything this test created.
        async with session_factory() as session:
            for statement in (
                "delete from completion_logs where behavior_id = :bid",
                "delete from scheduled_behaviors where behavior_id = :bid",
                "delete from objective_impacts where behavior_id = :bid",
                "delete from behaviors where id = :bid",
                "delete from optimization_runs where id = :rid",
                "delete from objectives where user_id = :uid",
                "delete from users where id = :uid",
            ):
                await session.execute(
                    text(statement),
                    {"bid": str(behavior_id), "rid": str(run_id), "uid": str(user_id)},
                )
            await session.commit()
