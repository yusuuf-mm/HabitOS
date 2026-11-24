"""Week preview/apply: seven real day-solves, no writes until explicit accept.

The preview is a read-only what-if over the dates the user can still plan. Each
day uses the same problem builder and solver as the existing routes, so the
numbers shown come from the same data and the same saved objective weights.
Apply re-checks a fingerprint of those inputs, re-runs the identical solves and
writes every day in one transaction; any failure rolls the whole week back.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock, settings
from app.core.constants import MINUTES_PER_PERIOD, PERIODS_PER_DAY, period_to_time
from app.core.exceptions import (
    InfeasibleProblemError,
    SolverBusyError,
    SolverError,
    SolverTimeoutError,
    UnboundedProblemError,
)
from app.models import (
    Behavior,
    CompletionLog,
    Constraint,
    Objective,
    OptimizationRun,
    ScheduledBehavior,
    User,
)
from app.optimization import (
    CandidateSolver,
    normalise_weights,
    record_weights,
    run_in_solver_pool,
)
from app.optimization.models import OptimizationProblem, OptimizationSolution, ScheduleItem
from app.schemas.optimization import (
    WeekApplyRequest,
    WeekApplyResult,
    WeekDayApplyResult,
    WeekDayResult,
    WeekPlanningError,
    WeekPreviewResult,
    WeekSession,
    WeekSessionMove,
    WeekSessionSlot,
)
from app.services.day_problem import load_day_problem
from app.services.metrics import local_today, resolve_day_plan, user_zone

logger = logging.getLogger(__name__)


@dataclass
class CurrentSession:
    """A session in the plan the user currently sees for a day."""

    planned_session_id: UUID
    behavior_id: UUID
    behavior_name: str
    time_period: int
    duration: int
    released_at: datetime | None = None
    retired_revision: int | None = None


@dataclass
class PlannedSession:
    """A candidate session with the identity it will have if applied."""

    planned_session_id: UUID
    behavior_id: UUID
    behavior_name: str
    time_period: int
    duration: int


@dataclass
class DayInputs:
    """Everything needed to re-solve one plannable day."""

    day: date
    mode: str  # full | partial
    problem: OptimizationProblem
    raw_weights: dict[str, Any]
    current_sessions: list[CurrentSession]
    previous_run: OptimizationRun | None
    revision: int
    current_period: int | None = None
    frozen_periods: dict[int, dict[int, int]] | None = None
    previous_starts: dict[int, int] | None = None


@dataclass
class PreparedDay:
    """A solved day ready for either display or the single apply transaction."""

    inputs: DayInputs
    solution: OptimizationSolution
    planned: list[PlannedSession]
    added: list[WeekSession]
    moved: list[WeekSessionMove]
    dropped: list[WeekSession]


@dataclass
class WeekSnapshot:
    """A stable view of the inputs that determine a week's plans."""

    week_start: date
    today: date
    days: list[date]
    plannable: list[date]
    current: dict[date, list[CurrentSession]]
    inputs: dict[date, DayInputs]
    fingerprint: str


# -- input collection -----------------------------------------------------


def _planning_days(week_start: date, today: date) -> tuple[list[date], list[date]]:
    if week_start.weekday() != 0:
        raise HTTPException(
            status_code=422, detail="weekStart must be a Monday."
        )
    days = [week_start + timedelta(days=offset) for offset in range(7)]
    plannable = [day for day in days if day >= today]
    if not plannable:
        raise HTTPException(
            status_code=422,
            detail="This week is entirely in the past; choose the current or a future week.",
        )
    return days, plannable


def _slot(period: int, duration: int) -> WeekSessionSlot:
    """Render a real solver slot; no rounding or guessed times."""
    return WeekSessionSlot(
        startTime=period_to_time(period % PERIODS_PER_DAY),
        endTime=period_to_time(
            (period % PERIODS_PER_DAY) + duration // MINUTES_PER_PERIOD
        ),
        duration=duration,
    )


async def _latest_run(
    db: AsyncSession, user: User, day: date
) -> OptimizationRun | None:
    result = await db.execute(
        select(OptimizationRun)
        .where(
            (OptimizationRun.user_id == user.id)
            & (OptimizationRun.start_date <= day)
            & (OptimizationRun.end_date >= day)
            & (OptimizationRun.status == "completed")
        )
        .order_by(OptimizationRun.created_at.desc())
    )
    return result.scalars().first()


async def _current_sessions(
    db: AsyncSession, user: User, day: date
) -> tuple[OptimizationRun | None, list[CurrentSession]]:
    """The newest completed run for the date, as shown on the schedule page."""
    run = await _latest_run(db, user, day)
    if run is None:
        return None, []
    result = await db.execute(
        select(ScheduledBehavior, Behavior)
        .join(Behavior)
        .where(ScheduledBehavior.optimization_run_id == run.id)
        .order_by(ScheduledBehavior.time_period)
    )
    sessions = [
        CurrentSession(
            planned_session_id=sb.planned_session_id,
            behavior_id=behavior.id,
            behavior_name=behavior.name,
            time_period=sb.time_period % PERIODS_PER_DAY,
            duration=sb.scheduled_duration,
            released_at=sb.released_at,
            retired_revision=sb.retired_revision,
        )
        for sb, behavior in result.all()
    ]
    return run, sessions


def _behavior_input(behavior: Behavior):
    from app.optimization import BehaviorScheduleInput

    return BehaviorScheduleInput(
        id=behavior.id,
        name=behavior.name,
        min_duration=behavior.min_duration,
        typical_duration=behavior.typical_duration,
        max_duration=behavior.max_duration,
        energy_cost=behavior.energy_cost,
        impacts=behavior.get_all_impacts(),
        preferred_time_slots=[
            slot.value if hasattr(slot, "value") else slot
            for slot in behavior.preferred_time_slots
        ],
        protected=bool(getattr(behavior, "is_protected", False)),
    )


async def _full_inputs(
    db: AsyncSession, user: User, day: date, current: list[CurrentSession]
) -> DayInputs:
    problem, raw_weights = await load_day_problem(db, user, day)
    return DayInputs(
        day=day,
        mode="full",
        problem=problem,
        raw_weights=raw_weights,
        current_sessions=current,
        previous_run=None,
        revision=1,
    )


async def _partial_inputs(
    db: AsyncSession,
    user: User,
    day: date,
    plan_run: OptimizationRun,
    current: list[CurrentSession],
    now: datetime,
    tz: Any,
) -> DayInputs:
    """Freeze elapsed periods of today and re-solve the rest, as reoptimize does."""
    result = await db.execute(
        select(ScheduledBehavior, Behavior)
        .join(Behavior)
        .where(ScheduledBehavior.optimization_run_id == plan_run.id)
        .order_by(ScheduledBehavior.time_period)
    )
    all_items = result.all()

    completed_result = await db.execute(
        select(CompletionLog.behavior_id).where(
            (CompletionLog.user_id == user.id)
            & (CompletionLog.optimization_run_id == plan_run.id)
        )
    )
    completed_ids = {row[0] for row in completed_result.all()}

    now_local = now.astimezone(tz)
    current_period = (now_local.hour * 60 + now_local.minute) // MINUTES_PER_PERIOD

    frozen_periods: dict[int, dict[int, int]] = {}
    behaviors_db: list[Behavior] = []
    behavior_index: dict[UUID, int] = {}
    previous_starts: dict[int, int] = {}

    for sb, behavior in all_items:
        if behavior.id not in behavior_index:
            behavior_index[behavior.id] = len(behaviors_db)
            behaviors_db.append(behavior)
        idx = behavior_index[behavior.id]
        local_period = sb.time_period % PERIODS_PER_DAY
        blocks = sb.scheduled_duration // MINUTES_PER_PERIOD
        for offset in range(blocks):
            period = local_period + offset
            if period < current_period:
                frozen_periods.setdefault(idx, {})[period] = (
                    1 if behavior.id in completed_ids else 0
                )

    for sb, behavior in all_items:
        idx = behavior_index[behavior.id]
        local_start = sb.time_period % PERIODS_PER_DAY
        if local_start + sb.scheduled_duration // MINUTES_PER_PERIOD > current_period:
            ref = max(local_start, current_period)
            if idx not in previous_starts or ref < previous_starts[idx]:
                previous_starts[idx] = ref

    objectives_result = await db.execute(
        select(Objective).where(Objective.user_id == user.id)
    )
    raw_weights = {
        obj.type.value if hasattr(obj.type, "value") else str(obj.type): obj.weight
        for obj in objectives_result.scalars().all()
    }
    constraints_result = await db.execute(
        select(Constraint).where(
            (Constraint.user_id == user.id) & Constraint.is_active.is_(True)
        )
    )
    from app.optimization import ConstraintInput

    constraints = [
        ConstraintInput(
            type=c.type.value if hasattr(c.type, "value") else str(c.type),
            parameters=c.parameters,
            is_active=c.is_active,
        )
        for c in constraints_result.scalars().all()
    ]

    problem = OptimizationProblem(
        user_id=user.id,
        behaviors=[_behavior_input(behavior) for behavior in behaviors_db],
        objectives=normalise_weights(raw_weights),
        constraints=constraints,
        start_date=day,
        end_date=day,
        time_periods=PERIODS_PER_DAY,
    )
    problem.blocked_periods = frozenset(await _blocked_for(db, user, day))

    return DayInputs(
        day=day,
        mode="partial",
        problem=problem,
        raw_weights=raw_weights,
        current_sessions=current,
        previous_run=plan_run,
        revision=(plan_run.plan_revision or 1) + 1,
        current_period=current_period,
        frozen_periods=frozen_periods,
        previous_starts=previous_starts,
    )


async def _blocked_for(db: AsyncSession, user: User, day: date) -> set[int]:
    from app.services.items import blocked_periods_for_day

    return await blocked_periods_for_day(db, user.id, day)


async def build_week_snapshot(
    db: AsyncSession, user: User, week_start: date
) -> WeekSnapshot:
    """Collect all inputs once so preview and apply hash exactly the same state."""
    tz = user_zone(user)
    now = clock.now_utc()
    today = local_today(tz, now)
    days, plannable = _planning_days(week_start, today)

    current: dict[date, list[CurrentSession]] = {}
    inputs: dict[date, DayInputs] = {}
    for day in days:
        display_run, sessions = await _current_sessions(db, user, day)
        current[day] = sessions
        if day not in plannable:
            continue
        plan = await resolve_day_plan(db, user, day, now=now)
        if day == today and plan.frozen and plan.run is not None:
            inputs[day] = await _partial_inputs(
                db, user, day, plan.run, sessions, now, tz
            )
        else:
            inputs[day] = await _full_inputs(db, user, day, sessions)

    fingerprint = _fingerprint(user.id, week_start, days, current, inputs)
    return WeekSnapshot(
        week_start=week_start,
        today=today,
        days=days,
        plannable=plannable,
        current=current,
        inputs=inputs,
        fingerprint=fingerprint,
    )


# -- fingerprint ----------------------------------------------------------


def _session_payload(sessions: list[CurrentSession]) -> list[dict[str, Any]]:
    return [
        {
            "plannedSessionId": str(session.planned_session_id),
            "behaviorId": str(session.behavior_id),
            "timePeriod": session.time_period,
            "duration": session.duration,
            "releasedAt": session.released_at.isoformat()
            if session.released_at
            else None,
            "retiredRevision": session.retired_revision,
        }
        for session in sessions
    ]


def _problem_payload(inputs: DayInputs) -> dict[str, Any]:
    problem = inputs.problem
    return {
        "behaviors": [
            {
                "id": str(behavior.id),
                "name": behavior.name,
                "minDuration": behavior.min_duration,
                "typicalDuration": behavior.typical_duration,
                "maxDuration": behavior.max_duration,
                "energyCost": behavior.energy_cost,
                "impacts": dict(sorted(behavior.impacts.items())),
                "preferredTimeSlots": sorted(behavior.preferred_time_slots),
                "protected": behavior.protected,
            }
            for behavior in problem.behaviors
        ],
        "objectives": dict(sorted(inputs.raw_weights.items())),
        "constraints": [
            {
                "type": constraint.type,
                "parameters": constraint.parameters,
                "isActive": constraint.is_active,
            }
            for constraint in problem.constraints
        ],
        "blockedPeriods": sorted(int(period) for period in problem.blocked_periods),
        "startDate": problem.start_date.isoformat(),
        "endDate": problem.end_date.isoformat(),
        "mode": inputs.mode,
        "revision": inputs.revision,
        "currentPeriod": inputs.current_period,
        "frozenPeriods": (
            {
                str(behavior_idx): dict(sorted(periods.items()))
                for behavior_idx, periods in sorted(
                    (inputs.frozen_periods or {}).items()
                )
            }
            or None
        ),
        "previousStarts": (
            dict(sorted((inputs.previous_starts or {}).items())) or None
        ),
    }


def _fingerprint(
    user_id: UUID,
    week_start: date,
    days: list[date],
    current: dict[date, list[CurrentSession]],
    inputs: dict[date, DayInputs],
) -> str:
    payload = {
        "userId": str(user_id),
        "weekStart": week_start.isoformat(),
        "dates": [day.isoformat() for day in days],
        "current": {
            day.isoformat(): _session_payload(current.get(day, [])) for day in days
        },
        "problems": {
            day.isoformat(): _problem_payload(inputs[day])
            for day in sorted(inputs)
        },
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


# -- solving and diffing --------------------------------------------------


async def _solve_day(inputs: DayInputs, low_priority: bool) -> OptimizationSolution:
    solver = CandidateSolver(timeout_seconds=settings.OPTIMIZATION_TIMEOUT_SECONDS)
    if inputs.mode == "partial":
        return await run_in_solver_pool(
            solver.solve_partial_day,
            inputs.problem,
            uuid4(),
            inputs.frozen_periods or {},
            timeout_seconds=settings.OPTIMIZATION_TIMEOUT_SECONDS,
            low_priority=low_priority,
            previous_starts=inputs.previous_starts or {},
        )
    return await run_in_solver_pool(
        solver.solve,
        inputs.problem,
        uuid4(),
        timeout_seconds=settings.OPTIMIZATION_TIMEOUT_SECONDS,
        low_priority=low_priority,
    )


def _solve_error(exc: Exception) -> WeekPlanningError:
    if isinstance(exc, InfeasibleProblemError):
        return WeekPlanningError(code="infeasible", message=exc.detail)
    if isinstance(exc, UnboundedProblemError):
        return WeekPlanningError(code="unbounded", message=exc.detail)
    if isinstance(exc, SolverTimeoutError):
        return WeekPlanningError(code="timeout", message=exc.detail)
    if isinstance(exc, SolverError):
        return WeekPlanningError(code="solver_error", message=exc.detail)
    return WeekPlanningError(
        code="unavailable",
        message="This day could not be planned from the saved data.",
    )


def _protected_conflict_error(solution: OptimizationSolution) -> WeekPlanningError:
    details = (solution.diagnostics or {}).get("protected_conflict") or {}
    unplaced = details.get("unplaced", [])
    names = ", ".join(
        str(item.get("behaviorName") or item.get("name") or item)
        for item in unplaced
        if isinstance(item, dict)
    )
    message = "A protected habit cannot be placed on this day."
    if names:
        message += " Affected: " + names + "."
    return WeekPlanningError(code="protected_conflict", message=message)


def _attach_identities(
    items: list[ScheduleItem], current: list[CurrentSession]
) -> list[PlannedSession]:
    """Pair sessions per behaviour, in start order, so a move keeps its identity."""
    new_by_behavior: dict[UUID, list[ScheduleItem]] = {}
    for item in items:
        if not item.is_scheduled:
            continue
        new_by_behavior.setdefault(item.behavior_id, []).append(item)

    old_by_behavior: dict[UUID, list[CurrentSession]] = {}
    for session in current:
        old_by_behavior.setdefault(session.behavior_id, []).append(session)

    planned: list[PlannedSession] = []
    for behavior_id, new_items in new_by_behavior.items():
        new_items.sort(key=lambda item: item.time_period)
        old_sessions = sorted(
            old_by_behavior.get(behavior_id, []), key=lambda item: item.time_period
        )
        for index, item in enumerate(new_items):
            identity = (
                old_sessions[index].planned_session_id
                if index < len(old_sessions)
                else uuid4()
            )
            planned.append(
                PlannedSession(
                    planned_session_id=identity,
                    behavior_id=behavior_id,
                    behavior_name=item.behavior_name,
                    time_period=item.time_period,
                    duration=item.scheduled_duration,
                )
            )
    return planned


def _session_view(session: PlannedSession | CurrentSession) -> WeekSession:
    return WeekSession(
        plannedSessionId=session.planned_session_id,
        behaviorId=session.behavior_id,
        behaviorName=session.behavior_name,
        **_slot(session.time_period, session.duration).model_dump(),
    )


def _diff_sessions(
    current: list[CurrentSession], planned: list[PlannedSession]
) -> tuple[list[WeekSession], list[WeekSessionMove], list[WeekSession]]:
    planned_by_behavior: dict[UUID, list[PlannedSession]] = {}
    for session in planned:
        planned_by_behavior.setdefault(session.behavior_id, []).append(session)
    current_by_behavior: dict[UUID, list[CurrentSession]] = {}
    for session in current:
        current_by_behavior.setdefault(session.behavior_id, []).append(session)

    added: list[WeekSession] = []
    moved: list[WeekSessionMove] = []
    dropped: list[WeekSession] = []

    behavior_ids = set(planned_by_behavior) | set(current_by_behavior)
    for behavior_id in behavior_ids:
        new_sessions = sorted(
            planned_by_behavior.get(behavior_id, []), key=lambda item: item.time_period
        )
        old_sessions = sorted(
            current_by_behavior.get(behavior_id, []), key=lambda item: item.time_period
        )
        for index in range(max(len(new_sessions), len(old_sessions))):
            new = new_sessions[index] if index < len(new_sessions) else None
            old = old_sessions[index] if index < len(old_sessions) else None
            if new and not old:
                added.append(_session_view(new))
            elif old and not new:
                dropped.append(_session_view(old))
            elif new and old:
                same_slot = (
                    new.time_period == old.time_period
                    and new.duration == old.duration
                )
                if not same_slot:
                    moved.append(
                        WeekSessionMove(
                            plannedSessionId=old.planned_session_id,
                            behaviorId=behavior_id,
                            behaviorName=new.behavior_name or old.behavior_name,
                            before=_slot(old.time_period, old.duration),
                            after=_slot(new.time_period, new.duration),
                            **_slot(new.time_period, new.duration).model_dump(),
                        )
                    )
    return added, moved, dropped


def _unavailable_day(
    day: date, sessions: list[CurrentSession], error: WeekPlanningError, mode: str = "full"
) -> WeekDayResult:
    return WeekDayResult(
        date=day,
        mode=mode,
        available=False,
        error=error,
        sessionsBefore=len(sessions),
        minutesBefore=sum(session.duration for session in sessions),
    )


async def _prepare_day(
    inputs: DayInputs, low_priority: bool
) -> PreparedDay:
    solution = await _solve_day(inputs, low_priority=low_priority)
    if solution.status == "protected_conflict":
        raise ProtectedConflict(solution)
    planned = _attach_identities(solution.schedule_items, inputs.current_sessions)
    added, moved, dropped = _diff_sessions(inputs.current_sessions, planned)
    return PreparedDay(
        inputs=inputs,
        solution=solution,
        planned=planned,
        added=added,
        moved=moved,
        dropped=dropped,
    )


class ProtectedConflict(Exception):
    """A day whose protected habits cannot be placed is not a valid preview."""

    def __init__(self, solution: OptimizationSolution):
        self.solution = solution
        super().__init__("protected_conflict")


# -- public API -----------------------------------------------------------


async def preview_week(
    db: AsyncSession, user: User, week_start: date
) -> WeekPreviewResult:
    """Solve every plannable day without writing anything."""
    snapshot = await build_week_snapshot(db, user, week_start)
    results: list[WeekDayResult] = []

    for day in snapshot.days:
        sessions = snapshot.current.get(day, [])
        if day not in snapshot.inputs:
            results.append(
                _unavailable_day(
                    day,
                    sessions,
                    WeekPlanningError(
                        code="past_day", message="Past days are read-only."
                    ),
                )
            )
            continue
        try:
            prepared = await _prepare_day(snapshot.inputs[day], low_priority=True)
        except SolverBusyError as exc:
            raise HTTPException(
                status_code=503,
                detail=exc.detail,
                headers={"Retry-After": "2"},
            ) from exc
        except ProtectedConflict as exc:
            results.append(
                _unavailable_day(
                    day,
                    sessions,
                    _protected_conflict_error(exc.solution),
                    mode=snapshot.inputs[day].mode,
                )
            )
            continue
        except Exception as exc:  # a failed day must not look like zero changes
            logger.info("Week preview day %s unavailable: %s", day, exc)
            results.append(
                _unavailable_day(
                    day,
                    sessions,
                    _solve_error(exc),
                    mode=snapshot.inputs[day].mode,
                )
            )
            continue

        results.append(
            WeekDayResult(
                date=day,
                mode=prepared.inputs.mode,
                available=True,
                solverStatus=prepared.solution.status,
                sessionsBefore=len(sessions),
                sessionsAfter=len(prepared.planned),
                minutesBefore=sum(session.duration for session in sessions),
                minutesAfter=sum(session.duration for session in prepared.planned),
                added=prepared.added,
                moved=prepared.moved,
                dropped=prepared.dropped,
                declines=list(
                    (prepared.solution.diagnostics or {}).get("declines", [])
                ),
            )
        )

    return WeekPreviewResult(
        weekStart=week_start,
        generatedAt=clock.now_utc(),
        fingerprint=snapshot.fingerprint,
        days=results,
    )


def _persist_day(db: AsyncSession, user: User, prepared: PreparedDay) -> None:
    """Stage one day's run and sessions; the caller commits them all at once."""
    inputs = prepared.inputs
    solution = prepared.solution
    run = OptimizationRun(
        id=solution.optimization_run_id,
        user_id=user.id,
        status="completed" if solution.status == "optimal" else "feasible",
        solver="candidate",
        start_date=inputs.day,
        end_date=inputs.day,
        time_periods=PERIODS_PER_DAY,
        total_objective_value=solution.total_objective_value,
        execution_time_seconds=solution.execution_time_seconds,
        results=solution.to_dict(),
        diagnostics={
            **(solution.diagnostics or {}),
            "objective_weights": record_weights(inputs.raw_weights),
            "week_planning": {"mode": inputs.mode},
        },
        plan_revision=inputs.revision,
    )
    db.add(run)

    for session in prepared.planned:
        db.add(
            ScheduledBehavior(
                optimization_run_id=run.id,
                behavior_id=session.behavior_id,
                time_period=session.time_period,
                scheduled_duration=session.duration,
                is_scheduled=True,
                planned_session_id=session.planned_session_id,
                plan_revision=inputs.revision,
            )
        )

    # A partial day also retires the sessions the new revision drops. That needs
    # an async query, so _retire_dropped performs it just before the single commit.


async def _retire_dropped(
    db: AsyncSession, prepared: PreparedDay, revision: int
) -> None:
    inputs = prepared.inputs
    if inputs.mode != "partial" or inputs.previous_run is None:
        return
    carried = {session.planned_session_id for session in prepared.planned}
    result = await db.execute(
        select(ScheduledBehavior).where(
            ScheduledBehavior.optimization_run_id == inputs.previous_run.id
        )
    )
    for old in result.scalars().all():
        if old.planned_session_id not in carried:
            old.retired_revision = revision


async def apply_week(
    db: AsyncSession, user: User, request: WeekApplyRequest
) -> WeekApplyResult:
    """Revalidate, re-solve and persist all plannable days atomically."""
    snapshot = await build_week_snapshot(db, user, request.weekStart)
    if request.fingerprint != snapshot.fingerprint:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "week_plan_stale",
                "message": "The plan changed since the preview. Preview again before applying.",
            },
        )

    prepared_days: list[PreparedDay] = []
    unavailable: list[dict[str, Any]] = []
    for day in snapshot.plannable:
        try:
            prepared_days.append(
                await _prepare_day(snapshot.inputs[day], low_priority=True)
            )
        except SolverBusyError as exc:
            raise HTTPException(
                status_code=503,
                detail=exc.detail,
                headers={"Retry-After": "2"},
            ) from exc
        except ProtectedConflict as exc:
            unavailable.append(
                {
                    "date": day.isoformat(),
                    **_protected_conflict_error(exc.solution).model_dump(),
                }
            )
        except Exception as exc:
            logger.info("Week apply day %s unavailable: %s", day, exc)
            unavailable.append(
                {"date": day.isoformat(), **_solve_error(exc).model_dump()}
            )

    if unavailable:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "week_plan_unavailable",
                "message": "At least one day could not be planned; nothing was written.",
                "days": unavailable,
            },
        )

    try:
        applied: list[WeekDayApplyResult] = []
        for prepared in prepared_days:
            _persist_day(db, user, prepared)
            await _retire_dropped(db, prepared, prepared.inputs.revision)
            applied.append(
                WeekDayApplyResult(
                    date=prepared.inputs.day,
                    runId=prepared.solution.optimization_run_id,
                    planRevision=prepared.inputs.revision,
                    mode=prepared.inputs.mode,
                    added=len(prepared.added),
                    moved=len(prepared.moved),
                    dropped=len(prepared.dropped),
                )
            )
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Week apply failed; all day writes rolled back")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "week_apply_failed",
                "message": "The week could not be applied; no changes were saved.",
            },
        )

    return WeekApplyResult(
        weekStart=request.weekStart,
        fingerprint=request.fingerprint,
        appliedDays=len(applied),
        days=applied,
    )
