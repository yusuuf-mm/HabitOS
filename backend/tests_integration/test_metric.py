"""Completion-rate contract — docs/METRIC.md (v1, amended).

These assert the promises the document makes, not internal structure: what counts,
what leaves the denominator, what stays in it, and when the answer is null.
"""
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from app.services.metrics import (
    Metric,
    compute_day,
    compute_range,
    local_day_end,
    resolve_day_plan,
    session_start,
    user_zone,
)

UTC = timezone.utc
DAY = datetime.now(UTC).date()  # "today" so completion timestamps land inside the day


def _future_period(minutes_ahead: int = 120) -> int:
    """A session slot that has not started yet, whatever time the suite runs.

    The release and commit endpoints use the real clock, so a hard-coded period
    is only future before that hour. Near midnight there is no such slot left.
    """
    now = datetime.now(UTC)
    period = (now.hour * 60 + now.minute + minutes_ahead) // 15
    if period >= 96:
        pytest.skip("no future session slot left in the local day")
    return period


async def _get_user_id(client: AsyncClient) -> UUID:
    from app.core.security import verify_token

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


async def _run(db_session, user_id, revision=1, baseline=None, created_at=None):
    from app.models.optimization import OptimizationRun

    run = OptimizationRun(
        user_id=user_id,
        status="completed",
        solver="linear",
        start_date=DAY,
        end_date=DAY,
        time_periods=96,
        plan_revision=revision,
        baseline_revision=baseline,
        committed_at=datetime.now(UTC) if baseline is not None else None,
    )
    if created_at is not None:
        run.created_at = created_at
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


@pytest.mark.asyncio
async def test_rate_is_completed_over_baseline_minus_released(auth_client, db_session):
    from app.models import User

    user_id = await _get_user_id(auth_client)
    user = await db_session.get(User, user_id)
    behavior = await _behavior(db_session, user_id)
    run = await _run(db_session, user_id, baseline=1)
    sessions = [await _session(db_session, run.id, behavior.id, period=30 + i) for i in range(4)]
    await _complete(db_session, user_id, behavior.id, sessions[0], datetime.now(UTC))
    sessions[1].released_at = datetime.now(UTC)
    await db_session.commit()

    metric = await compute_day(db_session, user, DAY)
    assert (metric.baseline, metric.completed, metric.released) == (4, 1, 1)
    assert metric.completion_rate == pytest.approx(1 / 3)
    assert metric.released_ratio == pytest.approx(0.25)


@pytest.mark.asyncio
async def test_system_dropped_stays_in_denominator_and_is_reported(auth_client, db_session):
    from app.models import User

    user_id = await _get_user_id(auth_client)
    user = await db_session.get(User, user_id)
    behavior = await _behavior(db_session, user_id)
    run = await _run(db_session, user_id, baseline=1)
    sessions = [await _session(db_session, run.id, behavior.id, period=30 + i) for i in range(3)]
    await _complete(db_session, user_id, behavior.id, sessions[0], datetime.now(UTC))
    sessions[1].retired_revision = 2
    await db_session.commit()

    metric = await compute_day(db_session, user, DAY)
    assert metric.system_dropped == 1
    assert metric.denominator == 3, "a dropped session must stay in the denominator"
    assert metric.completion_rate == pytest.approx(1 / 3)
    assert metric.completion_rate_vs_feasible == pytest.approx(1 / 2)


@pytest.mark.asyncio
async def test_zero_denominator_returns_null_not_one(auth_client, db_session):
    from app.models import User

    user_id = await _get_user_id(auth_client)
    user = await db_session.get(User, user_id)
    behavior = await _behavior(db_session, user_id)
    run = await _run(db_session, user_id, baseline=1)
    session = await _session(db_session, run.id, behavior.id)
    session.released_at = datetime.now(UTC)
    await db_session.commit()

    metric = await compute_day(db_session, user, DAY)
    assert metric.completion_rate is None
    assert metric.released_ratio == pytest.approx(1.0)
    assert metric.completion_rate_vs_feasible is None


@pytest.mark.asyncio
async def test_late_completion_counts_and_is_flagged(auth_client, db_session):
    from app.models import User

    user_id = await _get_user_id(auth_client)
    user = await db_session.get(User, user_id)
    tz = user_zone(user)
    behavior = await _behavior(db_session, user_id)
    run = await _run(db_session, user_id, baseline=1)
    session = await _session(db_session, run.id, behavior.id, period=20, duration=15)  # 05:00
    # Completed at 23:00 local — long after its window, still before the day ends.
    late = datetime.combine(DAY, time(23, 0), tzinfo=tz).astimezone(UTC)
    await _complete(db_session, user_id, behavior.id, session, late)
    await db_session.commit()

    metric = await compute_day(db_session, user, DAY)
    assert metric.completed == 1
    assert metric.late == 1
    assert metric.completion_rate == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_completion_after_local_day_end_does_not_count(auth_client, db_session):
    from app.models import User

    user_id = await _get_user_id(auth_client)
    user = await db_session.get(User, user_id)
    tz = user_zone(user)
    behavior = await _behavior(db_session, user_id)
    run = await _run(db_session, user_id, baseline=1)
    session = await _session(db_session, run.id, behavior.id, period=20)
    after = local_day_end(DAY, tz) + timedelta(minutes=1)
    await _complete(db_session, user_id, behavior.id, session, after)
    await db_session.commit()

    metric = await compute_day(db_session, user, DAY)
    assert metric.completed == 0
    assert metric.missed == 1


@pytest.mark.asyncio
async def test_draft_before_freeze_is_open_and_not_a_baseline(auth_client, db_session):
    from app.models import User

    user_id = await _get_user_id(auth_client)
    user = await db_session.get(User, user_id)
    behavior = await _behavior(db_session, user_id)
    run = await _run(db_session, user_id, created_at=datetime.combine(DAY, time(4, 0), tzinfo=UTC))
    await _session(db_session, run.id, behavior.id, period=40)
    await db_session.commit()

    early = datetime.combine(DAY, time(4, 30), tzinfo=UTC)
    plan = await resolve_day_plan(db_session, user, DAY, now=early)
    assert plan.frozen is False and plan.source == "open"
    assert (await compute_day(db_session, user, DAY, now=early)).completion_rate is None

    # Still open after 05:00: the first session (10:00) has not started yet.
    between = datetime.combine(DAY, time(6, 0), tzinfo=UTC)
    assert (await resolve_day_plan(db_session, user, DAY, now=between)).frozen is False

    after_freeze = datetime.combine(DAY, time(10, 30), tzinfo=UTC)
    plan = await resolve_day_plan(db_session, user, DAY, now=after_freeze)
    assert plan.frozen is True and plan.run.id == run.id


@pytest.mark.asyncio
async def test_multi_day_rate_is_summed_not_averaged(auth_client, db_session):
    from app.models import User

    user_id = await _get_user_id(auth_client)
    user = await db_session.get(User, user_id)
    behavior = await _behavior(db_session, user_id)

    # Day one: 1 of 1. Day two: 1 of 10. Summed = 2/11, averaged would be 0.55.
    day_one = await _run(db_session, user_id, baseline=1)
    first = await _session(db_session, day_one.id, behavior.id, period=30)
    await _complete(
        db_session, user_id, behavior.id, first,
        datetime.combine(DAY - timedelta(days=1), time(9, 0), tzinfo=UTC),
    )
    day_one.start_date = DAY - timedelta(days=1)
    day_one.end_date = DAY - timedelta(days=1)
    first_day_log = True

    day_two = await _run(db_session, user_id, baseline=1)
    ten = [await _session(db_session, day_two.id, behavior.id, period=30 + i) for i in range(10)]
    await _complete(db_session, user_id, behavior.id, ten[0], datetime.now(UTC))
    await db_session.commit()
    assert first_day_log

    metric = await compute_range(db_session, user, [DAY - timedelta(days=1), DAY])
    assert metric.baseline == 11
    assert metric.completed == 2
    assert metric.completion_rate == pytest.approx(2 / 11)


@pytest.mark.asyncio
async def test_timezone_shifts_the_day_boundary(auth_client, db_session):
    """The same instant is a different local day for +14 and for UTC."""
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    from app.models import User

    try:
        ZoneInfo("Pacific/Kiritimati")
    except (ZoneInfoNotFoundError, ValueError):
        pytest.skip("no IANA timezone database on this machine")

    user_id = await _get_user_id(auth_client)
    user = await db_session.get(User, user_id)
    user.timezone = "Pacific/Kiritimati"  # UTC+14
    await db_session.commit()
    await db_session.refresh(user)

    utc_start = session_start(DAY, 20, ZoneInfo("UTC"))
    local_start = session_start(DAY, 20, user_zone(user))
    assert local_start == utc_start - timedelta(hours=14)
    assert local_day_end(DAY, user_zone(user)) == local_day_end(DAY, ZoneInfo("UTC")) - timedelta(hours=14)


@pytest.mark.asyncio
async def test_release_endpoint_removes_session_from_denominator(auth_client, db_session):
    from app.models import User

    user_id = await _get_user_id(auth_client)
    behavior = await _behavior(db_session, user_id)
    run = await _run(db_session, user_id, baseline=1)
    session = await _session(db_session, run.id, behavior.id, period=_future_period())
    run.start_date = run.end_date = datetime.now(UTC).date()
    await db_session.commit()

    resp = await auth_client.post(f"/api/v1/schedule/{session.id}/release")
    assert resp.status_code == 200, resp.text

    await db_session.refresh(session)
    assert session.released_at is not None

    user = await db_session.get(User, user_id)
    metric = await compute_day(db_session, user, run.start_date)
    assert metric.released == 1
    assert metric.completion_rate is None  # 0 left in the denominator


@pytest.mark.asyncio
async def test_commit_records_exactly_one_baseline_per_day(auth_client, db_session):
    from app.models.optimization import OptimizationRun
    from sqlalchemy import select

    user_id = await _get_user_id(auth_client)
    behavior = await _behavior(db_session, user_id)
    today = datetime.now(UTC).date()
    first = await _run(db_session, user_id, revision=1)
    first.start_date = first.end_date = today
    await _session(db_session, first.id, behavior.id, period=_future_period(180))
    second = await _run(db_session, user_id, revision=2)
    second.start_date = second.end_date = today
    await _session(db_session, second.id, behavior.id, period=_future_period(60))
    await db_session.commit()

    resp = await auth_client.post("/api/v1/schedule/commit")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["baseline_revision"] == 2

    baselined = (
        await db_session.execute(
            select(OptimizationRun).where(OptimizationRun.baseline_revision.is_not(None))
        )
    ).scalars().all()
    assert len(baselined) == 1 and baselined[0].id == second.id

    # Idempotent: committing again keeps the same baseline and never creates a second.
    again = await auth_client.post("/api/v1/schedule/commit")
    assert again.status_code == 200
    baselined = (
        await db_session.execute(
            select(OptimizationRun).where(OptimizationRun.baseline_revision.is_not(None))
        )
    ).scalars().all()
    assert len(baselined) == 1


@pytest.mark.asyncio
async def test_replan_never_shrinks_the_baseline(auth_client, db_session):
    """A re-plan adds a revision; the baseline set `C` stays exactly as committed."""
    from app.models import User
    from app.models.optimization import OptimizationRun
    from sqlalchemy import select

    user_id = await _get_user_id(auth_client)
    user = await db_session.get(User, user_id)
    behavior = await _behavior(db_session, user_id)
    today = datetime.now(UTC).date()
    baseline = await _run(db_session, user_id, baseline=1)
    baseline.start_date = baseline.end_date = today
    await _session(db_session, baseline.id, behavior.id, period=30, duration=30)
    await db_session.commit()

    before = await compute_day(db_session, user, today)
    assert before.baseline == 1

    resp = await auth_client.post("/api/v1/schedule/reoptimize")
    assert resp.status_code == 200, resp.text

    after = await compute_day(db_session, user, today)
    assert after.baseline == before.baseline, "re-planning must not change |C|"
    assert after.released == before.released

    runs = (
        await db_session.execute(select(OptimizationRun).order_by(OptimizationRun.created_at))
    ).scalars().all()
    revisions = [(run.plan_revision, run.baseline_revision) for run in runs]
    assert (1, 1) in revisions
    assert (2, None) in revisions, revisions


@pytest.mark.asyncio
async def test_replan_keeps_planned_session_id_across_revisions(auth_client, db_session):
    """Identity survives re-planning, so a moved session is still the same session."""
    from app.models.optimization import ScheduledBehavior
    from sqlalchemy import select

    user_id = await _get_user_id(auth_client)
    behavior = await _behavior(db_session, user_id)
    today = datetime.now(UTC).date()
    baseline = await _run(db_session, user_id, baseline=1)
    baseline.start_date = baseline.end_date = today
    original = await _session(db_session, baseline.id, behavior.id, period=30, duration=30)
    original_id = original.planned_session_id
    await db_session.commit()

    first = await auth_client.post("/api/v1/schedule/reoptimize")
    assert first.status_code == 200, first.text
    first_run_id = first.json()["data"]["new_run_id"]

    first_sessions = (
        await db_session.execute(
            select(ScheduledBehavior).where(
                ScheduledBehavior.optimization_run_id == UUID(first_run_id)
            )
        )
    ).scalars().all()
    assert first_sessions
    # The re-plan is a new revision, but the session it carried forward is the
    # same session: same id, whichever period it ended up in.
    assert {s.planned_session_id for s in first_sessions} == {original_id}
    assert {s.plan_revision for s in first_sessions} == {2}
