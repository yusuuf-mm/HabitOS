"""Dashboard data endpoints: /items/range and /analytics/series + summary days."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, verify_token
from app.models import User
from tests_integration.support import plan_day, plan_now


async def _get_user_id(client: AsyncClient) -> UUID:
    token = client.headers["Authorization"].replace("Bearer ", "")
    return UUID(verify_token(token)["sub"])


async def _behavior(db_session, user_id, name="Exercise", slots=("morning",)):
    from app.models import Behavior, BehaviorCategory

    behavior = Behavior(
        user_id=user_id,
        name=name,
        category=BehaviorCategory.HEALTH,
        min_duration=15,
        typical_duration=15,
        max_duration=60,
        energy_cost=1.0,
        preferred_time_slots=list(slots),
    )
    db_session.add(behavior)
    await db_session.flush()
    return behavior


async def _run(db_session, user_id, revision=1, baseline=None):
    from app.models.optimization import OptimizationRun

    today = plan_day()
    run = OptimizationRun(
        user_id=user_id,
        status="completed",
        solver="linear",
        start_date=today,
        end_date=today,
        time_periods=96,
        plan_revision=revision,
        baseline_revision=baseline,
        committed_at=plan_now() if baseline is not None else None,
    )
    db_session.add(run)
    await db_session.flush()
    return run


async def _session(db_session, run_id, behavior_id, period=40, duration=15, **kwargs):
    from app.models.optimization import ScheduledBehavior

    session = ScheduledBehavior(
        optimization_run_id=run_id,
        behavior_id=behavior_id,
        time_period=period,
        scheduled_duration=duration,
        plan_revision=kwargs.pop("plan_revision", 1),
        **kwargs,
    )
    db_session.add(session)
    await db_session.flush()
    return session


async def _complete(db_session, user_id, behavior_id, session, at):
    from app.models.tracking import CompletionLog

    log = CompletionLog(
        user_id=user_id,
        behavior_id=behavior_id,
        optimization_run_id=session.optimization_run_id,
        planned_session_id=session.planned_session_id,
        actual_duration=session.scheduled_duration,
        completed_at=at,
    )
    db_session.add(log)
    await db_session.flush()
    return log


async def _make_user_b(db_session: AsyncSession) -> tuple[User, str]:
    """A second active user plus a bearer token for them."""
    user = User(
        email="userb@example.com",
        username="userb@example.com",
        password_hash="not-a-real-hash",
        status="active",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user, create_access_token({"sub": str(user.id)})


async def test_range_returns_occurrences_across_days_sorted_private_included(
    auth_client: AsyncClient,
):
    day1 = plan_day() + timedelta(days=1)
    day2 = day1 + timedelta(days=1)
    day3 = day1 + timedelta(days=2)

    daily = await auth_client.post(
        "/api/v1/items",
        json={
            "kind": "commitment",
            "title": "Standup",
            "startDate": day1.isoformat(),
            "startTime": "08:00",
            "durationMinutes": 60,
            "recurrence": "daily",
            "runDays": 3,
        },
    )
    assert daily.status_code == 201, daily.text

    private = await auth_client.post(
        "/api/v1/items",
        json={
            "kind": "commitment",
            "title": "Secret",
            "isPrivate": True,
            "startDate": day2.isoformat(),
            "startTime": "09:00",
            "durationMinutes": 60,
            "recurrence": "once",
        },
    )
    assert private.status_code == 201, private.text

    deadline = await auth_client.post(
        "/api/v1/items",
        json={"kind": "deadline", "title": "File taxes", "dueOn": day3.isoformat()},
    )
    assert deadline.status_code == 201, deadline.text

    response = await auth_client.get(
        f"/api/v1/items/range?from={day1.isoformat()}&to={day3.isoformat()}"
    )
    assert response.status_code == 200, response.text
    entries = response.json()
    assert len(entries) == 5, entries

    standups = [entry for entry in entries if entry["title"] == "Standup"]
    assert [entry["date"] for entry in standups] == [
        day1.isoformat(),
        day2.isoformat(),
        day3.isoformat(),
    ], entries
    assert standups[0]["startTime"] == "08:00"
    assert standups[0]["endTime"] == "09:00"
    assert standups[0]["kind"] == "commitment"
    assert "warnings" in standups[0]

    secret = next(entry for entry in entries if entry["title"] == "Secret")
    assert secret["isPrivate"] is True
    assert secret["date"] == day2.isoformat()
    assert secret["startTime"] == "09:00"

    taxes = next(entry for entry in entries if entry["title"] == "File taxes")
    assert taxes["kind"] == "deadline"
    assert taxes["dueOn"] == day3.isoformat()
    assert taxes["date"] == day3.isoformat()
    assert taxes["warnings"] == []

    keys = [(entry["date"], entry.get("startTime") or "99:99") for entry in entries]
    assert keys == sorted(keys), entries


async def test_range_rejects_to_before_from_and_too_large(
    auth_client: AsyncClient,
):
    day1 = plan_day() + timedelta(days=1)

    backwards = await auth_client.get(
        f"/api/v1/items/range?from={day1.isoformat()}"
        f"&to={(day1 - timedelta(days=1)).isoformat()}"
    )
    assert backwards.status_code == 422, backwards.text

    too_large = await auth_client.get(
        f"/api/v1/items/range?from={day1.isoformat()}"
        f"&to={(day1 + timedelta(days=31)).isoformat()}"
    )
    assert too_large.status_code == 422, too_large.text
    assert "range too large" in too_large.text

    max_ok = await auth_client.get(
        f"/api/v1/items/range?from={day1.isoformat()}"
        f"&to={(day1 + timedelta(days=30)).isoformat()}"
    )
    assert max_ok.status_code == 200, max_ok.text
    assert max_ok.json() == []


async def test_range_cross_user_sees_nothing(
    auth_client: AsyncClient, db_session: AsyncSession
):
    day1 = plan_day() + timedelta(days=1)
    created = await auth_client.post(
        "/api/v1/items",
        json={
            "kind": "commitment",
            "title": "Mine",
            "startDate": day1.isoformat(),
            "startTime": "08:00",
            "durationMinutes": 60,
            "recurrence": "once",
        },
    )
    assert created.status_code == 201, created.text

    _, token_b = await _make_user_b(db_session)
    original = auth_client.headers.get("Authorization")
    auth_client.headers["Authorization"] = f"Bearer {token_b}"
    try:
        response = await auth_client.get(
            f"/api/v1/items/range?from={day1.isoformat()}&to={day1.isoformat()}"
        )
    finally:
        if original is None:
            auth_client.headers.pop("Authorization", None)
        else:
            auth_client.headers["Authorization"] = original
    assert response.status_code == 200, response.text
    assert response.json() == []


@pytest.mark.asyncio
async def test_series_matches_seeded_baseline(
    auth_client: AsyncClient, db_session: AsyncSession
):
    from app.models import User

    user_id = await _get_user_id(auth_client)
    user = await db_session.get(User, user_id)
    behavior = await _behavior(db_session, user_id)
    run = await _run(db_session, user_id, baseline=1)
    first = await _session(db_session, run.id, behavior.id, period=30, duration=30)
    await _session(db_session, run.id, behavior.id, period=32, duration=45)
    await _complete(db_session, user_id, behavior.id, first, plan_now())
    await db_session.commit()

    response = await auth_client.get("/api/v1/analytics/series?days=7")
    assert response.status_code == 200, response.text
    entries = response.json()
    assert len(entries) == 7, entries
    assert entries[-1]["date"] == plan_day().isoformat()
    assert [entry["date"] for entry in entries] == sorted(
        entry["date"] for entry in entries
    )

    today = entries[-1]
    assert today["completed"] == 1
    assert today["baseline"] == 2
    assert today["plannedMinutes"] == 75
    assert today["completionRate"] == pytest.approx(0.5)
    assert today["released"] == 0
    assert today["dropped"] == 0

    default = await auth_client.get("/api/v1/analytics/series")
    assert default.status_code == 200, default.text
    assert len(default.json()) == 7


@pytest.mark.asyncio
async def test_summary_days_param(auth_client: AsyncClient):
    response = await auth_client.get("/api/v1/analytics/summary?days=30")
    assert response.status_code == 200, response.text
    assert "stats" in response.json()["data"]

    default = await auth_client.get("/api/v1/analytics/summary")
    assert default.status_code == 200, default.text
    assert "stats" in default.json()["data"]
