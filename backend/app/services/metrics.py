"""Completion-rate metric — docs/METRIC.md v1 (amended).

One place decides what a session's state is and what the denominator is, so the
dashboard, the history view and the tests cannot drift apart. Nothing here writes
a status column: states are derived from the timestamps the schema stores.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing import Sequence
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.constants import MINUTES_PER_PERIOD
from app.models import CompletionLog, OptimizationRun, ScheduledBehavior
from app.models import User

UTC = timezone.utc
PLAN_DAY_START = time(5, 0)  # METRIC.md §2: plan-local day start


def _aware(value: datetime) -> datetime:
    """SQLite hands back naive datetimes; treat them as UTC."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def user_zone(user: User | None) -> tzinfo:
    """The user's plan-local timezone, falling back to UTC.

    A machine without a tz database (some Windows Pythons) raises for every name,
    so UTC is the safe fallback rather than a crash on the dashboard.
    """
    name = (getattr(user, "timezone", None) or "UTC").strip()
    if name.upper() in {"UTC", "ETC/UTC", "GMT", "Z"}:
        return timezone.utc
    try:
        return ZoneInfo(name)
    except Exception:  # unknown name or no tzdata installed
        return timezone.utc


def local_today(tz: tzinfo, now: datetime | None = None) -> date:
    return (now or clock.now_utc()).astimezone(tz).date()


def plan_day_start(day: date, tz: tzinfo) -> datetime:
    """05:00 plan-local on that day, in UTC."""
    return datetime.combine(day, PLAN_DAY_START, tzinfo=tz).astimezone(UTC)


def local_day_end(day: date, tz: tzinfo) -> datetime:
    """Midnight ending that local day, in UTC (late completions stop here)."""
    return (
        datetime.combine(day, time(0, 0), tzinfo=tz) + timedelta(days=1)
    ).astimezone(UTC)


def session_start(day: date, time_period: int, tz: tzinfo) -> datetime:
    midnight = datetime.combine(day, time(0, 0), tzinfo=tz)
    return (midnight + timedelta(minutes=time_period * MINUTES_PER_PERIOD)).astimezone(UTC)


def session_end(day: date, time_period: int, duration: int, tz: tzinfo) -> datetime:
    return session_start(day, time_period, tz) + timedelta(minutes=duration)


@dataclass
class DayPlan:
    """Which plan's sessions form the baseline for a day."""

    day: date
    run: OptimizationRun | None
    frozen: bool
    source: str  # committed | fallback | open | none


@dataclass
class Metric:
    """Counts and rates for one day or a range, per docs/METRIC.md §1 and §7."""

    baseline: int = 0
    completed: int = 0
    released: int = 0
    system_dropped: int = 0
    missed: int = 0
    late: int = 0
    added_after_baseline: int = 0
    source: str = "none"

    @property
    def denominator(self) -> int:
        return self.baseline - self.released

    @property
    def feasible(self) -> int:
        return self.baseline - self.released - self.system_dropped

    @property
    def completion_rate(self) -> float | None:
        if self.denominator <= 0:
            return None
        return self.completed / self.denominator

    @property
    def released_ratio(self) -> float | None:
        if self.baseline <= 0:
            return None
        return self.released / self.baseline

    @property
    def completion_rate_vs_feasible(self) -> float | None:
        if self.feasible <= 0:
            return None
        return self.completed / self.feasible

    def __add__(self, other: "Metric") -> "Metric":
        return Metric(
            baseline=self.baseline + other.baseline,
            completed=self.completed + other.completed,
            released=self.released + other.released,
            system_dropped=self.system_dropped + other.system_dropped,
            missed=self.missed + other.missed,
            late=self.late + other.late,
            added_after_baseline=self.added_after_baseline + other.added_after_baseline,
            source=other.source if other.baseline else self.source,
        )


async def day_runs(db: AsyncSession, user_id: UUID, day: date) -> list[OptimizationRun]:
    result = await db.execute(
        select(OptimizationRun)
        .where(
            (OptimizationRun.user_id == user_id)
            & (OptimizationRun.start_date <= day)
            & (OptimizationRun.end_date >= day)
        )
        .order_by(OptimizationRun.created_at)
    )
    return list(result.scalars().all())


async def _sessions_for(db: AsyncSession, run_ids: Sequence[UUID]) -> list[ScheduledBehavior]:
    if not run_ids:
        return []
    result = await db.execute(
        select(ScheduledBehavior)
        .where(ScheduledBehavior.optimization_run_id.in_(list(run_ids)))
        .order_by(ScheduledBehavior.time_period)
    )
    return list(result.scalars().all())


async def resolve_day_plan(
    db: AsyncSession,
    user: User,
    day: date,
    now: datetime | None = None,
) -> DayPlan:
    """The baseline plan for a day, or an open draft, per METRIC.md §2."""
    runs = await day_runs(db, user.id, day)
    if not runs:
        return DayPlan(day, None, False, "none")

    committed = [
        run
        for run in runs
        if run.baseline_revision is not None
        and run.plan_revision == run.baseline_revision
    ]
    if committed:
        return DayPlan(day, committed[-1], True, "committed")

    tz = user_zone(user)
    now = now or clock.now_utc()
    sessions = await _sessions_for(db, [run.id for run in runs])

    freeze_at = plan_day_start(day, tz)  # 05:00 local
    if sessions:
        first_start = min(session_start(day, sb.time_period, tz) for sb in sessions)
        freeze_at = max(freeze_at, first_start)

    if now < freeze_at:
        return DayPlan(day, None, False, "open")

    current = [run for run in runs if _aware(run.created_at) <= freeze_at]
    return DayPlan(day, (current or runs)[-1], True, "fallback")


async def compute_day(db: AsyncSession, user: User, day: date, now: datetime | None = None) -> Metric:
    """Counts for one day's baseline set. See METRIC.md §1, §3, §4."""
    plan = await resolve_day_plan(db, user, day, now=now)
    if plan.run is None:
        return Metric(source=plan.source)

    tz = user_zone(user)
    now = now or clock.now_utc()
    day_end = local_day_end(day, tz)

    sessions = await _sessions_for(db, [plan.run.id])
    session_ids = [sb.planned_session_id for sb in sessions]

    logs = []
    if session_ids:
        result = await db.execute(
            select(CompletionLog).where(
                (CompletionLog.user_id == user.id)
                & (CompletionLog.planned_session_id.in_(session_ids))
            )
        )
        logs = list(result.scalars().all())

    completed_at: dict[UUID, datetime] = {}
    for log in logs:
        when = _aware(log.completed_at)
        if when > day_end:  # METRIC.md §3.1: after the local day ends it is not a completion
            continue
        if log.planned_session_id not in completed_at or when < completed_at[log.planned_session_id]:
            completed_at[log.planned_session_id] = when

    metric = Metric(baseline=len(sessions), source=plan.source)

    for sb in sessions:
        finished_at = completed_at.get(sb.planned_session_id)
        if finished_at is not None:
            metric.completed += 1
            if finished_at > session_end(day, sb.time_period, sb.scheduled_duration, tz):
                metric.late += 1
        elif sb.released_at is not None:
            metric.released += 1
        elif sb.retired_revision is not None:
            metric.system_dropped += 1
        else:
            metric.missed += 1

    # Sessions planned after the baseline are reported, never counted (METRIC.md §4).
    baseline_ids = set(session_ids)
    baseline_revision = plan.run.plan_revision or 1
    for run in await day_runs(db, user.id, day):
        if run.id == plan.run.id or (run.plan_revision or 1) <= baseline_revision:
            continue
        for later in await _sessions_for(db, [run.id]):
            if later.planned_session_id not in baseline_ids:
                metric.added_after_baseline += 1

    return metric


async def compute_range(
    db: AsyncSession,
    user: User,
    days: Sequence[date],
    now: datetime | None = None,
) -> Metric:
    """Summed rate across days — never an average of daily percentages (§7)."""
    total = Metric()
    for day in days:
        total = total + await compute_day(db, user, day, now=now)
    return total


def recent_days(count: int, tz: tzinfo, now: datetime | None = None) -> list[date]:
    today = local_today(tz, now=now)
    return [today - timedelta(days=offset) for offset in range(count - 1, -1, -1)]
