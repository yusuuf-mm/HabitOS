"""One realistic day through the real routes: solve, commit, act, re-plan, rate.

Existing coverage drives each step in isolation (`test_metric.py` writes rows
directly; `test_protected.py`, `test_forced_include.py` and
`test_session_identity.py` each pin one route). This pins the whole flow the
metric promises in `docs/METRIC.md`: the baseline freezes at commit, a re-plan
carries sessions by their stable id, a completion counts, a release leaves the
denominator, and a session the re-plan can no longer fit stays in it as a
system drop.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient

from tests_integration.support import plan_day


async def _behavior(client: AsyncClient, name: str, *, slots: list[str], lo: int, hi: int) -> dict:
    response = await client.post(
        "/api/v1/behaviors",
        json={
            "name": name,
            "category": "health",
            "durationMin": lo,
            "durationMax": hi,
            "preferredTimeSlots": slots,
        },
    )
    assert response.status_code in (200, 201), response.text
    return response.json()["data"]


async def _schedule(client: AsyncClient) -> list[dict]:
    response = await client.get("/api/v1/schedule")
    assert response.status_code == 200, response.text
    return response.json()["data"]["scheduledBehaviors"]


@pytest.mark.asyncio
async def test_commit_flow_from_solve_to_rate(auth_client: AsyncClient, db_session):
    from app.core.security import verify_token
    from app.models import User
    from app.services.metrics import compute_day

    today = plan_day().isoformat()  # frozen noon; afternoon/evening still future
    walk = await _behavior(auth_client, "Afternoon Walk", slots=["afternoon"], lo=30, hi=60)
    read = await _behavior(auth_client, "Read", slots=["evening"], lo=30, hi=60)
    meditate = await _behavior(auth_client, "Meditate", slots=["evening"], lo=15, hi=30)

    solved = await auth_client.post("/api/v1/optimization/solve", json={"targetDate": today})
    assert solved.status_code == 200, solved.text
    first_items = await _schedule(auth_client)
    assert len(first_items) == 3, first_items
    first_ids = {item["plannedSessionId"] for item in first_items}
    by_behavior = {item["behaviorId"]: item for item in first_items}

    committed = await auth_client.post("/api/v1/schedule/commit")
    assert committed.status_code == 200, committed.text
    assert committed.json()["data"]["baseline_revision"] == 1

    # Act on the current plan: do one session, withdraw another while future.
    done = await auth_client.post(f"/api/v1/schedule/{by_behavior[walk['id']]['id']}/complete")
    assert done.status_code == 200, done.text
    freed = await auth_client.post(f"/api/v1/schedule/{by_behavior[read['id']]['id']}/release")
    assert freed.status_code == 200, freed.text

    # A re-plan of the frozen day carries every session by its stable id and
    # reports no disruption: nothing had to move.
    replanned = await auth_client.post("/api/v1/schedule/reoptimize")
    assert replanned.status_code == 200, replanned.text
    disruption = replanned.json()["data"]["disruption"]
    assert disruption["carried_sessions"] == 3, disruption
    assert disruption["minutes_shifted"] == 0, disruption
    second_items = await _schedule(auth_client)
    assert {item["plannedSessionId"] for item in second_items} == first_ids

    # All three compete for the two-hour midday window at 60 minutes each, and
    # Meditate is worth the least: the next re-plan fits two and drops it.
    objectives = await auth_client.get("/api/v1/behaviors/objectives")
    assert objectives.status_code == 200, objectives.text
    health_id = next(
        obj["id"] for obj in objectives.json()["data"] if obj["name"] == "health"
    )
    for behavior, score in ((walk, 1.0), (read, 1.0), (meditate, 0.1)):
        moved = await auth_client.put(
            f"/api/v1/behaviors/{behavior['id']}",
            json={
                "preferredTimeSlots": ["midday"],
                "durationMin": 60,
                "durationMax": 60,
                "objectiveImpacts": [
                    {"objectiveId": health_id, "impactScore": score}
                ],
            },
        )
        assert moved.status_code == 200, moved.text
    replanned2 = await auth_client.post("/api/v1/schedule/reoptimize")
    assert replanned2.status_code == 200, replanned2.text
    disruption2 = replanned2.json()["data"]["disruption"]
    assert disruption2["carried_sessions"] == 2, disruption2
    assert disruption2["minutes_shifted"] > 0, disruption2
    third_items = await _schedule(auth_client)
    assert {item["behaviorId"] for item in third_items} == {walk["id"], read["id"]}

    # The rate counts the baseline: 1 done of (3 promised − 1 released).
    token = auth_client.headers["Authorization"].replace("Bearer ", "")
    user = await db_session.get(User, UUID(verify_token(token)["sub"]))
    metric = await compute_day(db_session, user, plan_day())
    assert (metric.baseline, metric.completed, metric.released, metric.system_dropped) == (3, 1, 1, 1)
    assert metric.completion_rate == pytest.approx(0.5)
    assert metric.completion_rate_vs_feasible == pytest.approx(1.0)

    dashboard = await auth_client.get("/api/v1/analytics/summary")
    assert dashboard.status_code == 200, dashboard.text
    stats = dashboard.json()["data"]["stats"]
    assert stats["completionRate"] == pytest.approx(0.5)
    assert (stats["released"], stats["systemDropped"]) == (1, 1)
