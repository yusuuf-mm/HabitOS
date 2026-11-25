"""Week planning amendments: accepted dates, result diffs and protected today."""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core.exceptions import SolverBusyError
from app.main import app
from app.models import (
    Behavior,
    CompletionLog,
    ObjectiveImpact,
    ObjectiveType,
    OptimizationRun,
    ScheduledBehavior,
    User,
)
from app.optimization import executor
from app.optimization.models import OptimizationSolution, ScheduleItem
from app.services import week_planning
from app.services.metrics import compute_day
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


def _accepted(preview: dict) -> dict:
    available = [day for day in preview["days"] if day["available"]]
    return {
        "dates": [day["date"] for day in available],
        "expectedResults": {
            day["date"]: day["resultHash"] for day in available
        },
    }


async def _apply(client: AsyncClient, preview: dict, **overrides):
    payload = {
        "weekStart": preview["weekStart"],
        "fingerprint": preview["fingerprint"],
        **_accepted(preview),
    }
    payload.update(overrides)
    return await client.post("/api/v1/optimization/week/apply", json=payload)


def _conflict_solution() -> OptimizationSolution:
    return OptimizationSolution(
        optimization_run_id=uuid4(),
        status="protected_conflict",
        solver="candidate",
        total_objective_value=0.0,
        schedule_items=[],
        objective_contributions={},
        diagnostics={
            "protected_conflict": {"unplaced": [{"behaviorName": "Morning Walk"}]}
        },
    )


@pytest.mark.asyncio
async def test_week_preview_is_read_only_and_uses_each_target_date(
    auth_client: AsyncClient, db_session, monkeypatch
):
    """Preview writes nothing and solves the seven displayed dates, not one repeated day."""
    await _behavior(auth_client, "Morning Walk", slots=["morning"])
    await _behavior(auth_client, "Evening Read", slots=["evening"])
    before = await _run_count(db_session)

    seen: list = []
    original = week_planning.load_day_problem

    async def capture(db, user, day):
        seen.append(day)
        return await original(db, user, day)

    monkeypatch.setattr(week_planning, "load_day_problem", capture)

    preview = await _preview(auth_client, plan_day())
    expected_dates = [
        (plan_day() + timedelta(days=offset)).isoformat() for offset in range(7)
    ]

    assert preview["fingerprint"]
    assert preview["rangeStart"] == plan_day().isoformat()
    assert preview["rangeEnd"] == expected_dates[-1]
    assert [day["date"] for day in preview["days"]] == expected_dates
    assert sorted(str(day) for day in seen) == sorted(expected_dates)
    for day in preview["days"]:
        assert day["available"] is True, day
        assert day["sessionsAfter"] is not None, day
        assert day["minutesAfter"] is not None, day
        assert day["resultHash"], day
    assert preview["skippedDays"] == []
    assert await _run_count(db_session) == before


@pytest.mark.asyncio
async def test_zero_commitment_preview_has_identical_result_sha(
    auth_client: AsyncClient,
):
    """The same inputs must produce the same result hash, not just the same input hash."""
    await _behavior(auth_client, "Noon Walk", slots=["midday"])

    first = await _preview(auth_client, plan_day())
    second = await _preview(auth_client, plan_day())

    assert first["fingerprint"] == second["fingerprint"]
    assert [day["resultHash"] for day in first["days"]] == [
        day["resultHash"] for day in second["days"]
    ]


@pytest.mark.asyncio
async def test_week_apply_accepts_fresh_preview_and_future_days_are_drafts(
    auth_client: AsyncClient, db_session
):
    """A fresh preview writes all days and future schedule rows are labelled drafts."""
    await _behavior(auth_client, "Noon Walk", slots=["midday"])
    preview = await _preview(auth_client, plan_day())

    applied = await _apply(auth_client, preview)

    assert applied.status_code == 200, applied.text
    data = applied.json()["data"]
    assert data["appliedDays"] == 7
    assert len(data["days"]) == 7
    assert data["skippedDays"] == []
    assert await _run_count(db_session) == 7

    future = (plan_day() + timedelta(days=3)).isoformat()
    schedule = await auth_client.get(f"/api/v1/schedule?date={future}")
    assert schedule.status_code == 200, schedule.text
    payload = schedule.json()["data"]
    assert payload["scheduledBehaviors"]
    assert payload["planSource"] == "draft"


@pytest.mark.asyncio
async def test_future_draft_is_visible_on_schedule(
    auth_client: AsyncClient, db_session
):
    """A future week run is schedule-visible but labelled as a draft."""
    user_id = await _user_id(auth_client)
    behavior = Behavior(
        user_id=user_id,
        name="Draft Walk",
        category="health",
        min_duration=15,
        typical_duration=15,
        max_duration=30,
        energy_cost=1.0,
        preferred_time_slots=["flexible"],
    )
    db_session.add(behavior)
    await db_session.flush()
    day = plan_day() + timedelta(days=4)
    run = OptimizationRun(
        user_id=user_id,
        status="completed",
        solver="candidate",
        start_date=day,
        end_date=day,
        time_periods=96,
        plan_revision=1,
    )
    db_session.add(run)
    await db_session.flush()
    db_session.add(
        ScheduledBehavior(
            optimization_run_id=run.id,
            behavior_id=behavior.id,
            time_period=48,
            scheduled_duration=30,
            is_scheduled=True,
            planned_session_id=uuid4(),
        )
    )
    await db_session.commit()

    schedule = await auth_client.get(f"/api/v1/schedule?date={day.isoformat()}")

    assert schedule.status_code == 200, schedule.text
    payload = schedule.json()["data"]
    assert payload["scheduledBehaviors"]
    assert payload["planSource"] == "draft"


@pytest.mark.asyncio
async def test_stale_fingerprint_writes_nothing(auth_client: AsyncClient, db_session):
    """A changed input fingerprint still blocks the apply."""
    await _behavior(auth_client, "Noon Walk", slots=["midday"])
    preview = await _preview(auth_client, plan_day())

    stale = await _apply(auth_client, preview, fingerprint="not-the-preview-fingerprint")

    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"]["code"] == "week_plan_stale"
    assert await _run_count(db_session) == 0


@pytest.mark.asyncio
async def test_changed_commitment_returns_409_with_the_new_diff(
    auth_client: AsyncClient, db_session
):
    """Apply re-solves: a changed commitment must return a new diff, not write."""
    await _behavior(auth_client, "Noon Walk", slots=["midday"])
    preview = await _preview(auth_client, plan_day())
    first_day = preview["days"][0]
    assert first_day["added"], first_day
    start_time = first_day["added"][0]["startTime"]

    commitment = await auth_client.post(
        "/api/v1/items",
        json={
            "kind": "commitment",
            "title": "Changed call",
            "startDate": first_day["date"],
            "startTime": start_time,
            "durationMinutes": 30,
            "recurrence": "once",
        },
    )
    assert commitment.status_code == 201, commitment.text

    changed = await _apply(auth_client, preview)

    assert changed.status_code == 409, changed.text
    detail = changed.json()["detail"]
    assert detail["code"] == "week_plan_changed", detail
    assert detail["days"][0]["diff"]
    assert detail["days"][0]["actualResultHash"] != first_day["resultHash"]
    assert await _run_count(db_session) == 0


@pytest.mark.asyncio
async def test_busy_and_conflict_days_are_skipped_but_other_days_apply(
    auth_client: AsyncClient, db_session, monkeypatch
):
    """A failed day is Unavailable with a reason; apply still writes the solved days."""
    await _behavior(auth_client, "Noon Walk", slots=["midday"])
    busy_day = plan_day() + timedelta(days=1)
    conflict_day = plan_day() + timedelta(days=2)
    original = week_planning._prepare_day

    async def flaky(inputs, low_priority):
        if inputs.day == busy_day:
            raise SolverBusyError("Solver busy")
        if inputs.day == conflict_day:
            raise week_planning.ProtectedConflict(_conflict_solution())
        return await original(inputs, low_priority)

    monkeypatch.setattr(week_planning, "_prepare_day", flaky)

    preview = await _preview(auth_client, plan_day())
    by_date = {day["date"]: day for day in preview["days"]}
    assert by_date[busy_day.isoformat()]["available"] is False
    assert by_date[busy_day.isoformat()]["error"]["code"] == "solver_busy"
    assert by_date[busy_day.isoformat()]["sessionsAfter"] is None
    assert by_date[conflict_day.isoformat()]["error"]["code"] == "protected_conflict"
    assert {skip["date"] for skip in preview["skippedDays"]} == {
        busy_day.isoformat(),
        conflict_day.isoformat(),
    }

    applied = await _apply(auth_client, preview)

    assert applied.status_code == 200, applied.text
    data = applied.json()["data"]
    assert data["appliedDays"] == 5
    assert {skip["date"] for skip in data["skippedDays"]} == {
        busy_day.isoformat(),
        conflict_day.isoformat(),
    }
    assert await _run_count(db_session) == 5


@pytest.mark.asyncio
async def test_25_behaviour_cap_is_an_unavailable_reason(
    auth_client: AsyncClient,
):
    """The cap is surfaced as a reason rather than an empty zero-change day."""
    for index in range(26):
        await _behavior(auth_client, f"Habit {index:02d}", slots=["flexible"])

    preview = await _preview(auth_client, plan_day())

    assert any(
        day["available"] is False
        and day["error"]["code"] == "solver_error"
        and "25" in day["error"]["message"]
        for day in preview["days"]
    ), preview["days"]


@pytest.mark.asyncio
async def test_saturated_solver_pool_makes_every_day_unavailable_with_503(
    auth_client: AsyncClient,
):
    """Holding the reserved worker makes each week day a solver-busy 503 result."""
    await _behavior(auth_client, "Morning Walk", slots=["morning"])
    assert SolverBusyError().status_code == 503

    gate = threading.Event()

    def held_solve():
        gate.wait(timeout=10)
        return None

    held = asyncio.create_task(
        executor.run_in_solver_pool(held_solve, timeout_seconds=20)
    )
    try:
        for _ in range(100):
            if executor.active_solves() >= 1:
                break
            await asyncio.sleep(0.01)
        assert executor.active_solves() == 1

        preview = await _preview(auth_client, plan_day())

        solvable = [day for day in preview["days"] if day["available"]]
        assert solvable == [], preview["days"]
        for day in preview["days"]:
            assert day["error"]["code"] == "solver_busy", day
            assert "retry in a moment" in day["error"]["message"], day
    finally:
        gate.set()
        await held


@pytest.mark.asyncio
async def test_week_apply_rolls_back_all_accepted_days_when_a_write_fails(
    auth_client: AsyncClient, db_session, monkeypatch
):
    """One failed day must leave the database exactly as it was."""
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

    failed = await _apply(auth_client, preview)

    assert failed.status_code == 500, failed.text
    assert failed.json()["detail"]["code"] == "week_apply_failed"
    assert await _run_count(db_session) == 0


@pytest.mark.asyncio
async def test_partly_done_monday_preserves_protected_sessions_and_retires_dropped(
    auth_client: AsyncClient, db_session, monkeypatch
):
    """Completed, in-progress and released sessions never move or drop; others retire."""
    from app.core import clock

    user_id = await _user_id(auth_client)

    async def make_behavior(name: str) -> Behavior:
        behavior = Behavior(
            user_id=user_id,
            name=name,
            category="health",
            min_duration=15,
            typical_duration=15,
            max_duration=30,
            energy_cost=1.0,
            preferred_time_slots=["flexible"],
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
        await db_session.flush()
        return behavior

    completed_b = await make_behavior("Completed Walk")
    progress_b = await make_behavior("In Progress Walk")
    released_b = await make_behavior("Released Walk")
    dropped_b = await make_behavior("Droppable Walk")
    new_b = await make_behavior("New Evening Walk")

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

    def session(behavior: Behavior, period: int) -> ScheduledBehavior:
        row = ScheduledBehavior(
            optimization_run_id=baseline.id,
            behavior_id=behavior.id,
            time_period=period,
            scheduled_duration=30,
            is_scheduled=True,
            planned_session_id=uuid4(),
        )
        db_session.add(row)
        return row

    completed = session(completed_b, 32)  # 08:00, already done
    in_progress = session(progress_b, 47)  # 11:45-12:15, clock is 12:00
    released = session(released_b, 60)  # 15:00, released from the baseline
    dropped = session(dropped_b, 72)  # 18:00, safe to re-plan
    released.released_at = clock.now_utc()
    db_session.add(
        CompletionLog(
            user_id=user_id,
            behavior_id=completed_b.id,
            optimization_run_id=baseline.id,
            planned_session_id=completed.planned_session_id,
            actual_duration=30,
            completed_at=clock.now_utc(),
        )
    )
    # A duplicate log for the same planned session must not make it count twice.
    db_session.add(
        CompletionLog(
            user_id=user_id,
            behavior_id=completed_b.id,
            optimization_run_id=baseline.id,
            planned_session_id=completed.planned_session_id,
            actual_duration=25,
            completed_at=clock.now_utc() + timedelta(minutes=2),
        )
    )
    await db_session.commit()

    original_solve = week_planning._solve_day

    async def controlled_solve(inputs, low_priority):
        if inputs.day == plan_day():
            return OptimizationSolution(
                optimization_run_id=uuid4(),
                status="optimal",
                solver="candidate",
                total_objective_value=1.0,
                schedule_items=[
                    ScheduleItem(new_b.id, new_b.name, 84, 30, True)
                ],
                objective_contributions={},
                execution_time_seconds=0.01,
                diagnostics={},
            )
        return await original_solve(inputs, low_priority)

    monkeypatch.setattr(week_planning, "_solve_day", controlled_solve)

    preview = await _preview(auth_client, plan_day())
    today = preview["days"][0]
    protected_ids = {
        str(completed.planned_session_id),
        str(in_progress.planned_session_id),
        str(released.planned_session_id),
    }
    diff_ids = {
        item["plannedSessionId"]
        for item in today["added"] + today["moved"] + today["dropped"]
    }
    assert protected_ids.isdisjoint(diff_ids), today
    assert str(dropped.planned_session_id) in diff_ids
    # (b) The completed session is never reported as moved or dropped.
    assert str(completed.planned_session_id) not in {
        item["plannedSessionId"] for item in today["moved"]
    }
    assert str(completed.planned_session_id) not in {
        item["plannedSessionId"] for item in today["dropped"]
    }

    user = (await db_session.execute(select(User).where(User.id == user_id))).scalar_one()
    metric_before = await compute_day(db_session, user, plan_day())

    applied = await _apply(auth_client, preview)
    assert applied.status_code == 200, applied.text

    # (a) The completion follows planned_session_id into the new plan revision.
    schedule = await auth_client.get(f"/api/v1/schedule?date={plan_day().isoformat()}")
    assert schedule.status_code == 200, schedule.text
    completed_view = next(
        row
        for row in schedule.json()["data"]["scheduledBehaviors"]
        if row["plannedSessionId"] == str(completed.planned_session_id)
    )
    assert completed_view["isCompleted"] is True

    replanned = (
        await db_session.execute(
            select(OptimizationRun).where(
                OptimizationRun.user_id == user_id,
                OptimizationRun.start_date == plan_day(),
                OptimizationRun.id != baseline.id,
            )
        )
    ).scalars().one()
    carried = {
        str(row.planned_session_id)
        for row in (
            await db_session.execute(
                select(ScheduledBehavior).where(
                    ScheduledBehavior.optimization_run_id == replanned.id
                )
            )
        ).scalars().all()
    }
    assert protected_ids <= carried
    assert new_b.id in {
        row.behavior_id
        for row in (
            await db_session.execute(
                select(ScheduledBehavior).where(
                    ScheduledBehavior.optimization_run_id == replanned.id
                )
            )
        ).scalars().all()
    }

    await db_session.refresh(dropped)
    assert dropped.retired_revision == replanned.plan_revision

    # (a) The carried completion is counted once, despite the duplicate log.
    metric_after = await compute_day(db_session, user, plan_day())
    assert metric_after.completed == 1
    # (c) The carried sessions' health numbers do not change. The dropped
    # session legitimately moves from missed to system_dropped, so those two
    # counters are excluded here.
    for field in (
        "baseline",
        "completed",
        "released",
        "denominator",
        "completion_rate",
    ):
        assert getattr(metric_after, field) == getattr(metric_before, field), field
    assert metric_after.system_dropped == metric_before.system_dropped + 1


@pytest.mark.asyncio
async def test_past_week_is_reported_as_skipped_not_rejected(auth_client: AsyncClient):
    """A fully past week still shows its range and labels every day read-only."""
    week_start = plan_day() - timedelta(days=7)
    preview = await _preview(auth_client, week_start)

    assert preview["rangeStart"] == week_start.isoformat()
    assert preview["rangeEnd"] == (week_start + timedelta(days=6)).isoformat()
    assert len(preview["days"]) == 7
    assert all(day["available"] is False for day in preview["days"])
    assert all(
        skip["code"] == "past_day" for skip in preview["skippedDays"]
    )

    blocked = await _apply(auth_client, preview)

    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["code"] == "week_plan_unavailable"


@pytest.mark.asyncio
async def test_week_endpoints_do_not_expose_another_users_plan(
    auth_client: AsyncClient, db_session
):
    """A second user's week is scoped to them; another preview cannot be reused."""
    await _behavior(auth_client, "Private Walk", slots=["midday"])
    preview_a = await _preview(auth_client, plan_day())

    other = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    try:
        await other.post(
            "/api/v1/auth/register",
            json={
                "email": "second@example.com",
                "name": "Second User",
                "password": "Password123",
            },
        )
        login = await other.post(
            "/api/v1/auth/login",
            json={"email": "second@example.com", "password": "Password123"},
        )
        assert login.status_code == 200, login.text
        other.headers["Authorization"] = f"Bearer {login.json()['accessToken']}"
        await _behavior(other, "Other Walk", slots=["evening"])

        preview_b = await _preview(other, plan_day())
        assert preview_b["fingerprint"] != preview_a["fingerprint"]
        assert all(
            day["available"] is False or day["sessionsAfter"] is not None
            for day in preview_b["days"]
        )

        reused = await _apply(other, preview_a)
        assert reused.status_code == 409, reused.text
        assert reused.json()["detail"]["code"] in {
            "week_plan_stale",
            "week_plan_changed",
        }
        assert await _run_count(db_session) == 0
    finally:
        await other.aclose()
