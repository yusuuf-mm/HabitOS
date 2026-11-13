import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_update_inactive_behavior_requires_reactivation(auth_client: AsyncClient):
    """Editing a soft-deleted behavior returns 409 unless the request reactivates it."""
    create_resp = await auth_client.post(
        "/api/v1/behaviors",
        json={
            "name": "Inactive Edit",
            "category": "health",
            "energyCost": 1,
            "durationMin": 10,
            "durationMax": 20,
        },
    )
    assert create_resp.status_code == 201
    behavior_id = create_resp.json()["data"]["id"]

    delete_resp = await auth_client.delete(f"/api/v1/behaviors/{behavior_id}")
    assert delete_resp.status_code == 200

    blocked = await auth_client.put(
        f"/api/v1/behaviors/{behavior_id}", json={"name": "Renamed Inactive"}
    )
    assert blocked.status_code == 409
    assert "inactive" in blocked.json()["detail"].lower()

    # The rejected update must not have changed the row.
    get_resp = await auth_client.get(f"/api/v1/behaviors/{behavior_id}")
    assert get_resp.json()["data"]["name"] == "Inactive Edit"
    assert get_resp.json()["data"]["isActive"] is False

    reactivated = await auth_client.put(
        f"/api/v1/behaviors/{behavior_id}",
        json={"isActive": True, "name": "Renamed Inactive"},
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["data"]["isActive"] is True
    assert reactivated.json()["data"]["name"] == "Renamed Inactive"
