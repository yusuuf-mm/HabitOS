import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_solve_optimization(auth_client: AsyncClient):
    """Test running optimization."""
    # First create a behavior to solve for
    await auth_client.post(
        "/api/v1/behaviors",
        json={
            "name": "Work",
            "category": "productivity",
            "durationMin": 60,
            "durationMax": 240,
            "energyCost": 5,
        }
    )
    
    # Run optimization
    response = await auth_client.post(
        "/api/v1/optimization/solve",
        json={
            "targetDate": "2026-02-03",
            "maxExecutionTimeMs": 10000
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    result = data["data"]["run"]
    assert "id" in result
    assert "status" in result
    assert "scheduledBehaviors" in result

@pytest.mark.asyncio
async def test_get_optimization_history(auth_client: AsyncClient):
    """Test getting optimization history."""
    response = await auth_client.get("/api/v1/optimization/history")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data["data"]
    assert "total" in data["data"]
