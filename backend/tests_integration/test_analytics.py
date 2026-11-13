import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_analytics_summary(auth_client: AsyncClient):
    """Test getting analytics summary."""
    response = await auth_client.get("/api/v1/analytics/summary")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "stats" in data
    assert "todaySchedule" in data
    assert "recentBehaviors" in data

@pytest.mark.asyncio
async def test_get_analytics_details(auth_client: AsyncClient):
    """Test getting detailed analytics."""
    response = await auth_client.get("/api/v1/analytics?period=7d")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "behaviorCompletions" in data
    assert "objectiveProgress" in data
    assert "categoryDistribution" in data


@pytest.mark.asyncio
async def test_dashboard_total_behaviors_excludes_inactive(auth_client: AsyncClient):
    """totalBehaviors on the dashboard must count only active behaviors."""
    deactivated = await auth_client.post(
        "/api/v1/behaviors",
        json={
            "name": "Deactivated Habit",
            "category": "health",
            "energyCost": 1,
            "durationMin": 10,
            "durationMax": 20,
        },
    )
    assert deactivated.status_code == 201
    deactivated_id = deactivated.json()["data"]["id"]

    active = await auth_client.post(
        "/api/v1/behaviors",
        json={
            "name": "Active Habit",
            "category": "health",
            "energyCost": 1,
            "durationMin": 10,
            "durationMax": 20,
        },
    )
    assert active.status_code == 201

    assert (
        await auth_client.delete(f"/api/v1/behaviors/{deactivated_id}")
    ).status_code == 200

    response = await auth_client.get("/api/v1/analytics/summary")
    assert response.status_code == 200
    stats = response.json()["data"]["stats"]
    assert stats["totalBehaviors"] == 1
    assert stats["activeBehaviors"] == 1
