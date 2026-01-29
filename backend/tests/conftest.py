import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def test_user_data():
    """Test user data."""
    return {
        "email": "test@example.com",
        "username": "testuser",
        "password": "TestPassword123",
        "first_name": "Test",
        "last_name": "User",
    }


@pytest.fixture
def test_behavior_data():
    """Test behavior data."""
    return {
        "name": "Morning Exercise",
        "description": "30-minute morning workout",
        "category": "health",
        "min_duration": 20,
        "typical_duration": 30,
        "max_duration": 45,
        "energy_cost": 1.5,
        "impacts": {
            "health": 0.9,
            "productivity": 0.3,
            "learning": 0.0,
            "wellness": 0.8,
            "social": 0.1,
        },
    }
