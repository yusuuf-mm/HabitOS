import pytest
from httpx import AsyncClient

async def get_objective_id(auth_client: AsyncClient, objective_type: str) -> str:
    """Helper to get objective ID by type."""
    response = await auth_client.get("/api/v1/behaviors/objectives")
    assert response.status_code == 200
    data = response.json()["data"]
    for obj in data:
        if obj["name"].lower() == objective_type.lower():
            return obj["id"]
    return None

@pytest.mark.asyncio
async def test_create_behavior(auth_client: AsyncClient):
    """Test creating a behavior."""
    health_id = await get_objective_id(auth_client, "health")
    
    response = await auth_client.post(
        "/api/v1/behaviors",
        json={
            "name": "Morning Run",
            "description": "A refreshing morning run",
            "category": "health",
            "energyCost": 3,
            "durationMin": 30,
            "durationMax": 60,
            "preferredTimeSlots": ["morning"],
            "objectiveImpacts": [
                {"objectiveId": health_id, "impactScore": 0.8}
            ]
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    behavior = data["data"]
    assert behavior["name"] == "Morning Run"
    assert behavior["category"] == "health"
    assert any(i["objectiveId"] == health_id and i["impactScore"] == 0.8 for i in behavior["objectiveImpacts"])

@pytest.mark.asyncio
async def test_get_behaviors(auth_client: AsyncClient):
    """Test listing behaviors."""
    # Create one first
    await auth_client.post(
        "/api/v1/behaviors",
        json={
            "name": "Read Book",
            "category": "learning",
            "energyCost": 1,
            "durationMin": 15,
            "durationMax": 60,
        }
    )
    
    response = await auth_client.get("/api/v1/behaviors")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data["data"]
    assert len(data["data"]["data"]) >= 1

@pytest.mark.asyncio
async def test_update_behavior(auth_client: AsyncClient):
    """Test updating a behavior."""
    # Create
    create_resp = await auth_client.post(
        "/api/v1/behaviors",
        json={
            "name": "Meditation",
            "category": "wellness",
            "energyCost": 1,
            "durationMin": 10,
            "durationMax": 20,
        }
    )
    behavior_id = create_resp.json()["data"]["id"]
    
    # Update
    response = await auth_client.put(
        f"/api/v1/behaviors/{behavior_id}",
        json={"name": "Guided Meditation", "durationMax": 25}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "Guided Meditation"
    assert data["durationMax"] == 25

@pytest.mark.asyncio
async def test_delete_behavior(auth_client: AsyncClient):
    """Test deleting a behavior performs a soft delete."""
    # Create
    create_resp = await auth_client.post(
        "/api/v1/behaviors",
        json={
            "name": "Short Walk",
            "category": "health",
            "energyCost": 1,
            "durationMin": 5,
            "durationMax": 15,
        }
    )
    behavior_id = create_resp.json()["data"]["id"]
    
    # Delete
    response = await auth_client.delete(f"/api/v1/behaviors/{behavior_id}")
    assert response.status_code == 200
    assert response.json()["success"] is True
    
    # Behavior row remains (soft-deleted) but is inactive and hidden from lists
    get_resp = await auth_client.get(f"/api/v1/behaviors/{behavior_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["isActive"] is False

    list_resp = await auth_client.get("/api/v1/behaviors")
    assert list_resp.status_code == 200
    ids = [b["id"] for b in list_resp.json()["data"]["data"]]
    assert behavior_id not in ids


@pytest.mark.asyncio
async def test_soft_delete_behavior_preserves_history_and_completion_rate(
    auth_client: AsyncClient, db_session
):
    """Deleting a behavior with past completions must keep history and completion rate."""
    from datetime import date, datetime, timezone
    from sqlalchemy import select, func
    from app.models import CompletionLog, OptimizationRun, ScheduledBehavior

    # Create behavior
    create_resp = await auth_client.post(
        "/api/v1/behaviors",
        json={
            "name": "History Habit",
            "category": "health",
            "energyCost": 1,
            "durationMin": 15,
            "durationMax": 30,
        },
    )
    assert create_resp.status_code == 201
    behavior_id = create_resp.json()["data"]["id"]

    # Resolve user id
    from app.core.security import verify_token

    token = auth_client.headers["Authorization"].replace("Bearer ", "")
    user_id = verify_token(token)["sub"]

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

    sb = ScheduledBehavior(
        optimization_run_id=run.id,
        behavior_id=behavior_id,
        time_period=16,
        scheduled_duration=15,
    )
    db_session.add(sb)
    await db_session.flush()

    log = CompletionLog(
        user_id=user_id,
        behavior_id=behavior_id,
        optimization_run_id=run.id,
        actual_duration=15,
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(log)
    await db_session.commit()

    before_logs = await db_session.execute(
        select(func.count(CompletionLog.id)).where(CompletionLog.behavior_id == behavior_id)
    )
    before_scheduled = await db_session.execute(
        select(func.count(ScheduledBehavior.id)).where(ScheduledBehavior.behavior_id == behavior_id)
    )
    before_summary = await auth_client.get("/api/v1/analytics/summary")
    assert before_summary.status_code == 200
    before_rate = before_summary.json()["data"]["stats"]["completionRate"]

    delete_resp = await auth_client.delete(f"/api/v1/behaviors/{behavior_id}")
    assert delete_resp.status_code == 200

    after_logs = await db_session.execute(
        select(func.count(CompletionLog.id)).where(CompletionLog.behavior_id == behavior_id)
    )
    after_scheduled = await db_session.execute(
        select(func.count(ScheduledBehavior.id)).where(ScheduledBehavior.behavior_id == behavior_id)
    )
    after_summary = await auth_client.get("/api/v1/analytics/summary")
    assert after_summary.status_code == 200
    after_rate = after_summary.json()["data"]["stats"]["completionRate"]

    assert before_logs.scalar() == after_logs.scalar() == 1
    assert before_scheduled.scalar() == after_scheduled.scalar() == 1
    assert after_rate == before_rate

    # Historical schedule still renders the deactivated behavior
    today = date.today().isoformat()
    schedule_resp = await auth_client.get(f"/api/v1/schedule?date={today}")
    assert schedule_resp.status_code == 200
    items = schedule_resp.json()["data"]["scheduledBehaviors"]
    assert any(i["behaviorId"] == behavior_id for i in items)
    assert any(i["behavior"]["id"] == behavior_id for i in items)
