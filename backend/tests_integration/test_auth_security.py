"""Integration tests for the auth security fixes."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_refresh_rejects_access_token(client: AsyncClient):
    """An access token presented to /auth/refresh must be rejected with 401.

    Regression test: previously the refresh endpoint only verified the JWT
    signature, so a stolen access token could be used to mint a fresh one
    indefinitely.
    """
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "access-as-refresh@example.com",
            "name": "Test",
            "password": "Password123",
        },
    )
    access_token = reg.json()["accessToken"]

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refreshToken": access_token},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_accepts_valid_refresh_token(client: AsyncClient):
    """A real refresh token must still be accepted after the type check."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "refresh-ok@example.com",
            "name": "Test",
            "password": "Password123",
        },
    )
    refresh_token = reg.json()["refreshToken"]

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refreshToken": refresh_token},
    )
    assert response.status_code == 200
    assert "accessToken" in response.json()


@pytest.mark.asyncio
async def test_objective_impacts_roundtrip(auth_client: AsyncClient):
    """Creating a behavior with impacts should round-trip via the new table."""
    objectives_resp = await auth_client.get("/api/v1/behaviors/objectives")
    assert objectives_resp.status_code == 200
    objectives = objectives_resp.json()["data"]
    health = next(o for o in objectives if o["name"].lower() == "health")
    productivity = next(o for o in objectives if o["name"].lower() == "productivity")

    create = await auth_client.post(
        "/api/v1/behaviors",
        json={
            "name": "Jog",
            "category": "health",
            "energyCost": 3,
            "durationMin": 20,
            "durationMax": 45,
            "objectiveImpacts": [
                {"objectiveId": health["id"], "impactScore": 0.8},
                {"objectiveId": productivity["id"], "impactScore": 0.2},
            ],
        },
    )
    assert create.status_code == 201, create.text
    impacts = create.json()["data"]["objectiveImpacts"]
    by_id = {i["objectiveId"]: i["impactScore"] for i in impacts}
    assert by_id[health["id"]] == 0.8
    assert by_id[productivity["id"]] == 0.2

    # Update with a different impact set — old rows should be replaced, not
    # silently merged.
    update = await auth_client.put(
        f"/api/v1/behaviors/{create.json()['data']['id']}",
        json={
            "objectiveImpacts": [
                {"objectiveId": health["id"], "impactScore": 0.5},
            ],
        },
    )
    assert update.status_code == 200
    impacts2 = update.json()["data"]["objectiveImpacts"]
    by_id2 = {i["objectiveId"]: i["impactScore"] for i in impacts2}
    assert by_id2[health["id"]] == 0.5
    # Productivity row should have been removed.
    assert all(i["objectiveId"] != productivity["id"] for i in impacts2)
