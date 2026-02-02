import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_objectives(auth_client: AsyncClient):
    """Test listing user objectives."""
    response = await auth_client.get("/api/v1/behaviors/objectives")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    # Default objectives (health, productivity, learning, wellness, social)
    assert len(data["data"]) == 5
    types = [obj["name"] for obj in data["data"]]
    assert "health" in types
    assert "productivity" in types
