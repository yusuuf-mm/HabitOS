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
