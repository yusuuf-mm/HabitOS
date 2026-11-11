import pytest
from datetime import date
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select


@pytest.mark.asyncio
async def test_get_schedule(auth_client: AsyncClient):
    """Test getting daily schedule."""
    # First we need an optimization run to have a schedule
    # But for a basic test, even an empty one should return 200
    today = date.today().isoformat()
    response = await auth_client.get(f"/api/v1/schedule?date={today}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["date"] == today
    assert "scheduledBehaviors" in data


@pytest.mark.asyncio
async def test_mark_behavior_completion(auth_client: AsyncClient, db_session):
    """Test marking behavior as complete/incomplete."""
    # This requires more setup (behavior, optimization run, scheduled behavior)
    # For now, let's verify the endpoint structure even if it returns 404 for non-existent IDs
    invalid_id = "00000000-0000-0000-0000-000000000000"

    response = await auth_client.post(f"/api/v1/schedule/{invalid_id}/complete")
    assert response.status_code == 404

    response = await auth_client.post(f"/api/v1/schedule/{invalid_id}/incomplete")
    assert response.status_code == 404


async def _user_id_from_client(async_client: AsyncClient) -> UUID:
    from app.core.security import verify_token

    token = async_client.headers["Authorization"].replace("Bearer ", "")
    payload = verify_token(token)
    return UUID(payload["sub"])


@pytest.mark.asyncio
async def test_mark_complete_for_other_user_returns_404_and_creates_no_log(
    auth_client: AsyncClient, client: AsyncClient, db_session
):
    """User B must not be able to complete user A's scheduled behavior."""
    from app.models import Behavior, BehaviorCategory, OptimizationRun, ScheduledBehavior, CompletionLog

    user_a_id = await _user_id_from_client(auth_client)

    # Create user B
    register = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "userb@example.com",
            "name": "User B",
            "password": "Password123",
        },
    )
    assert register.status_code in (200, 201)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "userb@example.com", "password": "Password123"},
    )
    assert login.status_code == 200
    user_b_token = login.json()["accessToken"]

    behavior = Behavior(
        user_id=user_a_id,
        name="A's habit",
        category=BehaviorCategory.HEALTH,
        min_duration=15,
        typical_duration=15,
        max_duration=30,
        energy_cost=1.0,
        preferred_time_slots=["morning"],
    )
    db_session.add(behavior)
    await db_session.flush()

    run = OptimizationRun(
        user_id=user_a_id,
        status="completed",
        solver="linear",
        start_date=date.today(),
        end_date=date.today(),
        time_periods=96,
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

    resp = await client.post(
        f"/api/v1/schedule/{sb.id}/complete",
        headers={"Authorization": f"Bearer {user_b_token}"},
    )
    assert resp.status_code == 404

    logs = await db_session.execute(
        select(CompletionLog).where(CompletionLog.behavior_id == behavior.id)
    )
    assert logs.scalars().first() is None

