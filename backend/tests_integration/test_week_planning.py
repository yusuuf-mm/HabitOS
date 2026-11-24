"""Current Part B: preview seven days, then apply only after explicit accept."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from tests_integration.support import plan_day


async def _user_id(client: AsyncClient) -> UUID:
    from app.core.security import verify_token

    token = client.headers["Authorization"].replace("Bearer ", "")
    return UUID(verify_token(token)["sub"])


async def _behavior(
    client: AsyncClient,
    name: str,
    *,
    slots: list[str],
    lo: int = 15,
    hi: int = 30,
    impact: float = 1.0,
) -> dict:
    objectives = await client.get("/api/v1/behaviors/objectives")
    assert objectives.status_code == 200, objectives.text
    objective_id = next(
        item["id"] for item in objectives.json()["data"] if item["name"] == "health"
    )
    response = await client.post(
        "/api/v1/behaviors",
        json={
            "name": name,
            "category": "health",
            "durationMin": lo,
            "durationMax": hi,
            "preferredTimeSlots": slots,
            "objectiveImpacts": [
                {"objectiveId": objective_id, "impactScore": impact}
            ],
        },
    )
    assert response.status_code in (200, 201), response.text
    return response.json()["data"]


async def _run_count(db_session) -> int:
    from app.models import OptimizationRun

    result = await db_session.execute(
        select(func.count()).select_from(OptimizationRun)
    )
    return int(result.scalar() or 0)


async def _preview(client: AsyncClient, week_start):
    response = await client.post(
        "/api/v1/optimization/week/preview",
        json={"weekStart": week_start.isoformat()},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


@pytest.mark.asyncio
async def test_week_preview_is_read_only_and_reports_all_seven_days(
    auth_client: AsyncClient, db_session
):
    """Preview must produce real per-day diffs and write no runs."""
    await _behavior(auth_client, "Morning Walk", slots=["morning"])
    await _behavior(auth_client, "Evening Read", slots=["evening"])
    before = await _run_count(db_session)

    preview = await _preview(auth_client, plan_day())

    assert preview["fingerprint"]
    assert len(preview["days"]) == 7
    assert [day["date"] for day in preview["days"]] == [
        (plan_day() + timedelta(days=offset)).isoformat() for offset in range(7)
    ]
    for day in preview["days"]:
        assert day["available"] is True, day
        assert day["sessionsAfter"] is not None, day
        assert day["minutesAfter"] is not None, day
    assert await _run_count(db_session) == before


@pytest.mark.asyncio
async def test_week_apply_requires_a_fresh_fingerprint_then_writes_every_day(
    auth_client: AsyncClient, db_session
):
    """A stale preview writes nothing; an accepted preview writes all days."""
    await _behavior(auth_client, "Noon Walk", slots=["midday"])
    preview = await _preview(auth_client, plan_day())

    stale = await auth_client.post(
        "/api/v1/optimization/week/apply",
        json={
            "weekStart": plan_day().isoformat(),
            "fingerprint": "not-the-preview-fingerprint",
        },
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"]["code"] == "week_plan_stale"
    assert await _run_count(db_session) == 0

    applied = await auth_client.post(
        "/api/v1/optimization/week/apply",
        json={
            "weekStart": plan_day().isoformat(),
            "fingerprint": preview["fingerprint"],
        },
    )
    assert applied.status_code == 200, applied.text
    data = applied.json()["data"]
    assert data["appliedDays"] == 7
    assert len(data["days"]) == 7
    assert await _run_count(db_session) == 7

    future = (plan_day() + timedelta(days=3)).isoformat()
    schedule = await auth_client.get(f"/api/v1/schedule?date={future}")
    assert schedule.status_code == 200, schedule.text
    assert schedule.json()["data"]["scheduledBehaviors"]


@pytest.mark.asyncio
async def test_week_apply_rolls_back_all_days_when_a_write_fails(
    auth_client: AsyncClient, db_session, monkeypatch
):
    """One failed day must leave the database exactly as it was."""
    from app.services import week_planning

    await _behavior(auth_client, "Quick Walk", slots=["flexible"], lo=15, hi=15)
    preview = await _preview(auth_client, plan_day())

    original = week_planning._persist_day
    calls = {"count": 0}

    def flaky(db, user, prepared):
        calls["count"] += 1
        if calls["count"] == 4:
            raise RuntimeError("simulated write failure")
        return original(db, user, prepared)

    monkeypatch.setattr(week_planning, "_persist_day", flaky)

    failed = await auth_client.post(
        "/api/v1/optimization/week/apply",
        json={
            "weekStart": plan_day().isoformat(),
            "fingerprint": preview["fingerprint"],
        },
    )
    assert failed.status_code == 500, failed.text
    assert failed.json()["detail"]["code"] == "week_apply_failed"
    assert await _run_count(db_session) == 0


@pytest.mark.asyncio
async def test_partial_today_replans_without_changing_session_identity(
    auth_client: AsyncClient, db_session
):
    """A frozen today is re-planned as the next revision, carrying its session id."""
    from app.models import Behavior, ObjectiveImpact, ObjectiveType
    from app.models.optimization import OptimizationRun, ScheduledBehavior

    user_id = await _user_id(auth_client)
    behavior = Behavior(
        user_id=user_id,
        name="Afternoon Walk",
        category="health",
        min_duration=15,
        typical_duration=15,
        max_duration=30,
        energy_cost=2.0,
        preferred_time_slots=["afternoon"],
    )
    db_session.add(behavior)
    await db_session.flush()
    db_session.add(
        ObjectiveImpact(
            behavior_id=behavior.id,
            objective_type=ObjectiveType.HEALTH,
            impact_score=1.0,
        )
    )
    baseline = OptimizationRun(
        user_id=user_id,
        status="completed",
        solver="candidate",
        start_date=plan_day(),
        end_date=plan_day(),
        time_periods=96,
        baseline_revision=1,
        plan_revision=1,
    )
    db_session.add(baseline)
    await db_session.flush()
    original_session = ScheduledBehavior(
        optimization_run_id=baseline.id,
        behavior_id=behavior.id,
        time_period=32,  # 08:00, before the frozen fixed clock at noon
        scheduled_duration=30,
    )
    db_session.add(original_session)
    await db_session.commit()

    preview = await _preview(auth_client, plan_day())
    today_result = preview["days"][0]
    assert today_result["mode"] == "partial", today_result

    applied = await auth_client.post(
        "/api/v1/optimization/week/apply",
        json={
            "weekStart": plan_day().isoformat(),
            "fingerprint": preview["fingerprint"],
        },
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["data"]["days"][0]["planRevision"] == 2

    runs = (
        await db_session.execute(
            select(OptimizationRun)
            .where(OptimizationRun.user_id == user_id)
            .order_by(OptimizationRun.created_at)
        )
    ).scalars().all()
    assert len(runs) == 8  # the baseline plus seven applied days
    replanned = next(
        run
        for run in runs
        if run.start_date == plan_day() and run.id != baseline.id
    )
    assert replanned.plan_revision == 2

    sessions = (
        await db_session.execute(
            select(ScheduledBehavior).where(
                ScheduledBehavior.optimization_run_id == replanned.id
            )
        )
    ).scalars().all()
    assert original_session.planned_session_id in {
        session.planned_session_id for session in sessions
    }


@pytest.mark.asyncio
async def test_past_week_is_rejected_without_solving(auth_client: AsyncClient):
    """Past days are read-only; the API says so instead of returning a blank week."""
    response = await auth_client.post(
        "/api/v1/optimization/week/preview",
        json={"weekStart": (plan_day() - timedelta(days=7)).isoformat()},
    )
    assert response.status_code == 422, response.text
