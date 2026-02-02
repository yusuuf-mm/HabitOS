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
    """Test deleting a behavior."""
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
    assert response.status_code == 200 # Changed from 204 to 200 because of ApiResponse
    assert response.json()["success"] is True
    
    # Verify deleted
    get_resp = await auth_client.get(f"/api/v1/behaviors/{behavior_id}")
    assert get_resp.status_code == 404
