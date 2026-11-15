"""Route contract for the what-if solve and editable objective weights."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _behavior(client: AsyncClient, name: str, slots: list[str], lo: int = 30, hi: int = 60) -> str:
    response = await client.post(
        "/api/v1/behaviors",
        json={
            "name": name,
            "category": "productivity",
            "durationMin": lo,
            "durationMax": hi,
            "preferredTimeSlots": slots,
        },
    )
    assert response.status_code in (200, 201), response.text
    return response.json()["data"]["id"]


@pytest.mark.asyncio
async def test_forced_include_reports_cost_and_uses_the_pool(auth_client: AsyncClient):
    requested = await _behavior(auth_client, "Deep Work", ["midday"], 60, 60)
    await _behavior(auth_client, "Calls", ["midday"], 60, 60)
    await _behavior(auth_client, "Admin", ["midday"], 60, 60)

    response = await auth_client.post(
        "/api/v1/optimization/forced-include",
        json={"targetDate": "2026-07-06", "behaviorIds": [requested]},
    )
    assert response.status_code == 200, response.text
    result = response.json()["data"]

    assert result["fits"] is True
    assert [item["behaviorId"] for item in result["forced"]] == [requested]
    assert result["forced"][0]["duration"] % 15 == 0
    assert result["forced"][0]["startTime"] < result["forced"][0]["endTime"]
    # The plan value change is reported from the emitted schedule, and the
    # penalised solver value is a separate number.
    assert "objectiveChange" in result
    assert result.get("solverObjective") is not None
    for displaced in result["displaced"]:
        assert displaced["reason"] in {"no_fit", "over_capacity", "preempted_by_protected"}
    assert isinstance(result["relaxations"], list)


@pytest.mark.asyncio
async def test_forced_include_rejects_an_unknown_behaviour(auth_client: AsyncClient):
    await _behavior(auth_client, "Known", ["morning"])
    response = await auth_client.post(
        "/api/v1/optimization/forced-include",
        json={"behaviorIds": ["11111111-1111-1111-1111-111111111111"]},
    )
    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_forced_include_needs_a_behaviour(auth_client: AsyncClient):
    response = await auth_client.post(
        "/api/v1/optimization/forced-include", json={"behaviorIds": []}
    )
    assert response.status_code == 422, response.text
    assert "at least one behaviour" in response.json()["detail"]


@pytest.mark.asyncio
async def test_objective_weights_are_editable_and_normalised(auth_client: AsyncClient):
    listed = await auth_client.get("/api/v1/behaviors/objectives")
    assert listed.status_code == 200, listed.text
    objectives = listed.json()["data"]
    assert objectives, "a new user must have default objectives"
    assert abs(sum(o["weight"] for o in objectives) - 1.0) < 1e-6

    target = objectives[0]
    updated = await auth_client.put(
        f"/api/v1/behaviors/objectives/{target['id']}", json={"weight": 5.0}
    )
    assert updated.status_code == 200, updated.text
    weights = {o["name"]: o["weight"] for o in updated.json()["data"]}
    assert abs(sum(weights.values()) - 1.0) < 1e-6, weights
    assert weights[target["name"]] > 0.5, "the edited objective must dominate"


@pytest.mark.asyncio
async def test_plan_records_the_weights_it_used(auth_client: AsyncClient, db_session):
    from uuid import UUID

    from sqlalchemy import select

    from app.models.optimization import OptimizationRun

    await _behavior(auth_client, "Read", ["evening"])
    solved = await auth_client.post(
        "/api/v1/optimization/solve", json={"targetDate": "2026-07-07"}
    )
    assert solved.status_code == 200, solved.text
    run_id = UUID(solved.json()["data"]["run"]["id"])

    run = (
        await db_session.execute(select(OptimizationRun).where(OptimizationRun.id == run_id))
    ).scalars().first()
    recorded = run.diagnostics["objective_weights"]
    assert abs(sum(recorded["normalised"].values()) - 1.0) < 1e-6
    assert recorded["raw"], "the raw weights are kept for audit"
    assert run.diagnostics["formulation"] == "candidate"
