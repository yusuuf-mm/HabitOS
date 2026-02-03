import pytest
from httpx import AsyncClient
from datetime import date

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
