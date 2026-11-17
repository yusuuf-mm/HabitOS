"""Protected habits through the API: flagged, placed first, conflicts surfaced."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _behavior(
    client: AsyncClient,
    name: str,
    *,
    slots: list[str],
    lo: int,
    hi: int,
    protected: bool = False,
) -> str:
    response = await client.post(
        "/api/v1/behaviors",
        json={
            "name": name,
            "category": "health",
            "durationMin": lo,
            "durationMax": hi,
            "preferredTimeSlots": slots,
            "isProtected": protected,
        },
    )
    assert response.status_code in (200, 201), response.text
    return response.json()["data"]["id"]


@pytest.mark.asyncio
async def test_flag_round_trips(auth_client: AsyncClient):
    created = await auth_client.post(
        "/api/v1/behaviors",
        json={
            "name": "Hospital",
            "category": "health",
            "durationMin": 30,
            "durationMax": 30,
            "preferredTimeSlots": ["morning"],
            "isProtected": True,
        },
    )
    assert created.status_code in (200, 201), created.text
    assert created.json()["data"]["isProtected"] is True

    listed = await auth_client.get("/api/v1/behaviors")
    assert listed.status_code == 200
    assert listed.json()["data"]["data"][0]["isProtected"] is True


@pytest.mark.asyncio
async def test_a_protected_habit_that_cannot_fit_is_a_conflict(auth_client: AsyncClient):
    # Two hours of midday holds one 120-minute session; two protected habits do not fit.
    await _behavior(auth_client, "Hospital A", slots=["midday"], lo=120, hi=120, protected=True)
    await _behavior(auth_client, "Hospital B", slots=["midday"], lo=120, hi=120, protected=True)

    response = await auth_client.post(
        "/api/v1/optimization/solve", json={"targetDate": "2026-07-06"}
    )
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "protected_conflict"
    assert detail["unplaced"], "the unplaced protected habit must be named"
    assert detail["minimalRelaxation"], "the smallest relaxation must be named"

    # No half-plan was persisted.
    history = await auth_client.get("/api/v1/optimization/history")
    assert history.json()["data"]["total"] == 0


@pytest.mark.asyncio
async def test_protected_habits_that_fit_are_all_planned(auth_client: AsyncClient):
    first = await _behavior(
        auth_client, "Hospital A", slots=["morning"], lo=30, hi=30, protected=True
    )
    second = await _behavior(
        auth_client, "Hospital B", slots=["morning"], lo=30, hi=30, protected=True
    )
    await _behavior(auth_client, "Read", slots=["morning"], lo=60, hi=60)

    response = await auth_client.post(
        "/api/v1/optimization/solve", json={"targetDate": "2026-07-07"}
    )
    assert response.status_code == 200, response.text
    scheduled = {
        item["behaviorId"]
        for item in response.json()["data"]["schedule"]["scheduledBehaviors"]
    }
    assert {first, second} <= scheduled
