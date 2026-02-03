import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    """Test user registration."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "name": "Test User",
            "password": "Password123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "accessToken" in data
    assert "user" in data
    assert data["user"]["email"] == "test@example.com"
    assert data["user"]["name"] == "Test User"

@pytest.mark.asyncio
async def test_login_user(client: AsyncClient):
    """Test user login."""
    # First register
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "login@example.com",
            "name": "Login User",
            "password": "Password123"
        }
    )
    
    # Then login
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "login@example.com",
            "password": "Password123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "accessToken" in data
    assert "refreshToken" in data

@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    """Test login with invalid credentials."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "WrongPassword"
        }
    )
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    """Test token refresh."""
    # Register and get tokens
    reg_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "refresh@example.com",
            "name": "Refresh User",
            "password": "Password123"
        }
    )
    refresh_token = reg_response.json()["refreshToken"]
    
    # Refresh
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refreshToken": refresh_token}
    )
    assert response.status_code == 200
    assert "accessToken" in response.json()
