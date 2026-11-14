"""Session identity across a re-plan.

The metric in docs/METRIC.md counts sessions against a frozen baseline, which only
works if (a) every session has its own identity, (b) a completion can name that
identity, and (c) a re-plan is visibly a later revision than the plan it replaced.
"""
from datetime import date, datetime, timezone
from uuid import UUID

import pytest
from httpx import AsyncClient


async def _get_user_id(client: AsyncClient) -> UUID:
    """Extract the user ID from the JWT in the client headers."""
    from app.core.security import verify_token

    token = client.headers["Authorization"].replace("Bearer ", "")
    return UUID(verify_token(token)["sub"])


@pytest.mark.asyncio
async def test_replan_increments_plan_revision_on_run_and_sessions(
    auth_client: AsyncClient, db_session
):
    """A re-plan is revision N+1, and its sessions say so too."""
    from app.models import Behavior, BehaviorCategory, ObjectiveType, ObjectiveImpact
    from app.models.optimization import OptimizationRun, ScheduledBehavior

    user_id = await _get_user_id(auth_client)

    behavior = Behavior(
        user_id=user_id,
        name="Exercise",
        category=BehaviorCategory.HEALTH,
        min_duration=30,
        typical_duration=30,
        max_duration=60,
        energy_cost=3.0,
        preferred_time_slots=["morning"],
    )
    db_session.add(behavior)
    await db_session.flush()
    db_session.add(
        ObjectiveImpact(
            behavior_id=behavior.id, objective_type=ObjectiveType.HEALTH, impact_score=0.9
        )
    )

    first_run = OptimizationRun(
        user_id=user_id,
        status="completed",
        solver="linear",
        start_date=date.today(),
        end_date=date.today(),
        time_periods=96,
        results={"objective_contributions": {"health": {"contribution": 27.0, "weight": 1.0}}},
        total_objective_value=27.0,
    )
    db_session.add(first_run)
    await db_session.flush()

    db_session.add(
        ScheduledBehavior(
            optimization_run_id=first_run.id,
            behavior_id=behavior.id,
            time_period=30,  # 07:30, inside the morning window
            scheduled_duration=30,
        )
    )
    await db_session.commit()

    resp = await auth_client.post("/api/v1/schedule/reoptimize")
    assert resp.status_code == 200, resp.text
    new_run_id = resp.json()["data"]["new_run_id"]

    from sqlalchemy import select

    runs = (
        await db_session.execute(
            select(OptimizationRun).order_by(OptimizationRun.created_at)
        )
    ).scalars().all()
    by_id = {str(run.id): run for run in runs}
    assert by_id[str(first_run.id)].plan_revision == 1
    assert by_id[new_run_id].plan_revision == 2

    sessions = (
        await db_session.execute(
            select(ScheduledBehavior).order_by(ScheduledBehavior.plan_revision)
        )
    ).scalars().all()
    assert sessions, "the re-plan produced no sessions"

    new_sessions = [s for s in sessions if str(s.optimization_run_id) == new_run_id]
    assert new_sessions, "the new run has no sessions"
    for session in new_sessions:
        assert session.plan_revision == 2, (
            f"session {session.id} stamped {session.plan_revision}, run is 2"
        )

    # Identity is per session, and unique across the whole day's plans.
    ids = [s.planned_session_id for s in sessions]
    assert all(pid is not None for pid in ids)
    assert len(ids) == len(set(ids)), "two sessions share a planned_session_id"


@pytest.mark.asyncio
async def test_completion_can_point_at_one_session(auth_client: AsyncClient, db_session):
    """A completion binds to a single session, not merely to its behaviour."""
    from sqlalchemy import select

    from app.models import Behavior, BehaviorCategory
    from app.models.optimization import OptimizationRun, ScheduledBehavior
    from app.models.tracking import CompletionLog

    user_id = await _get_user_id(auth_client)

    behavior = Behavior(
        user_id=user_id,
        name="Read",
        category=BehaviorCategory.LEARNING,
        min_duration=15,
        typical_duration=15,
        max_duration=30,
        energy_cost=1.0,
        preferred_time_slots=["evening"],
    )
    db_session.add(behavior)
    await db_session.flush()

    run = OptimizationRun(
        user_id=user_id,
        status="completed",
        solver="linear",
        start_date=date.today(),
        end_date=date.today(),
        time_periods=96,
    )
    db_session.add(run)
    await db_session.flush()

    # The same behaviour scheduled twice: two promises, two identities.
    first = ScheduledBehavior(
        optimization_run_id=run.id,
        behavior_id=behavior.id,
        time_period=64,
        scheduled_duration=15,
    )
    second = ScheduledBehavior(
        optimization_run_id=run.id,
        behavior_id=behavior.id,
        time_period=70,
        scheduled_duration=15,
    )
    db_session.add_all([first, second])
    await db_session.commit()

    assert first.planned_session_id != second.planned_session_id

    log = CompletionLog(
        user_id=user_id,
        behavior_id=behavior.id,
        optimization_run_id=run.id,
        planned_session_id=second.planned_session_id,
        actual_duration=15,
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(log)
    await db_session.commit()

    stored = (
        await db_session.execute(
            select(CompletionLog).where(CompletionLog.id == log.id)
        )
    ).scalar_one()
    assert stored.planned_session_id == second.planned_session_id
    assert stored.planned_session_id != first.planned_session_id

    # And the join the metric relies on resolves to exactly one session.
    joined = (
        await db_session.execute(
            select(ScheduledBehavior).where(
                ScheduledBehavior.planned_session_id == stored.planned_session_id
            )
        )
    ).scalars().all()
    assert [s.id for s in joined] == [second.id]
