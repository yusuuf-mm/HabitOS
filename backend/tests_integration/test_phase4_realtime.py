"""Phase 4 integration tests — WebSocket broadcast + partial-day re-optimization + telemetry."""
import asyncio
from datetime import date, datetime, timezone
from unittest.mock import patch, AsyncMock
from uuid import UUID

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# WS broadcast test — verifies the manager's method is called by patching it.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_broadcast_called_on_complete(auth_client: AsyncClient, db_session):
    """Verify broadcast_schedule_update invoked on behavior completion."""
    from app.models import Behavior, BehaviorCategory, ObjectiveType, ObjectiveImpact
    from app.models.optimization import OptimizationRun, ScheduledBehavior

    user_id = await _get_user_id(auth_client)

    behavior = Behavior(
        user_id=user_id,
        name="Meditate",
        category=BehaviorCategory.HEALTH,
        min_duration=15,
        typical_duration=15,
        max_duration=30,
        energy_cost=1.0,
        preferred_time_slots=["morning"],
    )
    db_session.add(behavior)
    await db_session.flush()

    impact = ObjectiveImpact(behavior_id=behavior.id, objective_type=ObjectiveType.HEALTH, impact_score=1.0)
    db_session.add(impact)
    await db_session.flush()

    run = OptimizationRun(
        user_id=user_id,
        status="completed",
        solver="linear",
        start_date=date.today(),
        end_date=date.today(),
        time_periods=96,
        results={"objective_contributions": {"health": {"contribution": 15.0, "weight": 1.0}}},
        total_objective_value=15.0,
    )
    db_session.add(run)
    await db_session.flush()

    sb = ScheduledBehavior(
        optimization_run_id=run.id,
        behavior_id=behavior.id,
        time_period=16,
        scheduled_duration=15,
    )
    db_session.add(sb)
    await db_session.commit()

    from app.api.v1.ws import manager

    with patch.object(manager, "broadcast_schedule_update", new_callable=AsyncMock) as mock_broadcast:
        resp = await auth_client.post(f"/api/v1/schedule/{sb.id}/complete")
        assert resp.status_code == 200
        mock_broadcast.assert_called_once()


@pytest.mark.asyncio
async def test_broadcast_called_on_incomplete(auth_client: AsyncClient, db_session):
    """Verify broadcast_schedule_update invoked on behavior incomplete."""
    from app.models import Behavior, BehaviorCategory, ObjectiveType, ObjectiveImpact
    from app.models.optimization import OptimizationRun, ScheduledBehavior
    from app.models.tracking import CompletionLog

    user_id = await _get_user_id(auth_client)

    behavior = Behavior(
        user_id=user_id,
        name="Read",
        category=BehaviorCategory.LEARNING,
        min_duration=15,
        typical_duration=30,
        max_duration=60,
        energy_cost=0.5,
        preferred_time_slots=["evening"],
    )
    db_session.add(behavior)
    await db_session.flush()

    impact = ObjectiveImpact(behavior_id=behavior.id, objective_type=ObjectiveType.MINDFULNESS, impact_score=0.8)
    db_session.add(impact)
    await db_session.flush()

    run = OptimizationRun(
        user_id=user_id,
        status="completed",
        solver="linear",
        start_date=date.today(),
        end_date=date.today(),
        time_periods=96,
        results={"objective_contributions": {"mind": {"contribution": 24.0, "weight": 1.0}}},
        total_objective_value=24.0,
    )
    db_session.add(run)
    await db_session.flush()

    sb = ScheduledBehavior(
        optimization_run_id=run.id,
        behavior_id=behavior.id,
        time_period=64,
        scheduled_duration=30,
    )
    db_session.add(sb)
    await db_session.flush()

    log = CompletionLog(
        user_id=user_id,
        behavior_id=behavior.id,
        optimization_run_id=run.id,
        actual_duration=30,
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(log)
    await db_session.commit()

    from app.api.v1.ws import manager

    with patch.object(manager, "broadcast_schedule_update", new_callable=AsyncMock) as mock_broadcast:
        resp = await auth_client.post(f"/api/v1/schedule/{sb.id}/incomplete")
        assert resp.status_code == 200
        mock_broadcast.assert_called_once()


# ---------------------------------------------------------------------------
# Partial-day re-optimization test
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_partial_reoptimize_returns_new_run(auth_client: AsyncClient, db_session):
    """Verify /schedule/reoptimize returns a new run."""
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

    impact = ObjectiveImpact(behavior_id=behavior.id, objective_type=ObjectiveType.HEALTH, impact_score=0.9)
    db_session.add(impact)
    await db_session.flush()

    run = OptimizationRun(
        user_id=user_id,
        status="completed",
        solver="linear",
        start_date=date.today(),
        end_date=date.today(),
        time_periods=96,
        results={"objective_contributions": {"health": {"contribution": 60.0, "weight": 1.0}}},
        total_objective_value=60.0,
    )
    db_session.add(run)
    await db_session.flush()

    sb = ScheduledBehavior(
        optimization_run_id=run.id,
        behavior_id=behavior.id,
        time_period=80,
        scheduled_duration=30,
    )
    db_session.add(sb)
    await db_session.commit()

    resp = await auth_client.post("/api/v1/schedule/reoptimize")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["new_run_id"] is not None
    assert body["data"]["status"] in ("optimal", "feasible")
    assert isinstance(body["data"]["schedule"], list)


# ---------------------------------------------------------------------------
# Telemetry trend test
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_telemetry_trend_empty(auth_client: AsyncClient):
    """Verify /telemetry/trend returns empty list when no records exist."""
    resp = await auth_client.get("/api/v1/telemetry/trend?days=7")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _get_user_id(client: AsyncClient) -> UUID:
    """Extract the user ID from the JWT in the client headers."""
    from app.core.security import verify_token
    token = client.headers["Authorization"].replace("Bearer ", "")
    payload = verify_token(token)
    return UUID(payload["sub"])
