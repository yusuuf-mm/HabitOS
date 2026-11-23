"""Item routes: commitments and deadlines (docs/ITEMS.md)."""
import dataclasses
import logging
from datetime import datetime, timedelta
from datetime import date
from typing import List
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.api.v1.optimization import _load_problem
from app.core import settings
from app.core.exceptions import (
    SolverBusyError,
    SolverError,
    InfeasibleProblemError,
    UnboundedProblemError,
    SolverTimeoutError,
)
from app.models import User
from app.models.item import Item
from app.optimization import CandidateSolver, run_in_solver_pool
from app.schemas.item import ItemCreate, ItemResponse, ItemUpdate
from app.services.items import (
    blocked_periods_for_day,  # noqa: F401  (shared helper lives here)
    get_owned_item,
    item_to_response,
    list_owned_items,
    occurrence_on,
    warnings_for,
)
from app.services.metrics import user_zone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/items", tags=["items"])

try:
    from app.schemas.item import _parse_start_time as _schema_parse_start_time
except ImportError:  # pragma: no cover - schema parser is the normal path
    _schema_parse_start_time = None


def _parse_time(value: str):
    """Parse "HH:MM" to a time (schema parser when importable)."""
    if _schema_parse_start_time is not None:
        return _schema_parse_start_time(value)
    return datetime.strptime(value.strip(), "%H:%M").time()


def _weekdays_to_bitmask(days: List[int]) -> int:
    """Weekday list (Mon=0) -> bitmask (Mon -> bit 1)."""
    return sum(1 << d for d in (days or []))


def _resolve_recurrence_until(payload: ItemCreate):
    """Explicit recurrenceUntil wins; runDays derives startDate + N - 1."""
    if payload.recurrenceUntil is not None:
        return payload.recurrenceUntil
    if payload.runDays is not None and payload.startDate is not None:
        return payload.startDate + timedelta(days=payload.runDays - 1)
    if payload.kind == "commitment":
        return payload.startDate
    return None


async def _create_item(
    db: AsyncSession, current_user: User, payload: ItemCreate
) -> ItemResponse:
    """Shared creation logic for POST "" and POST "/confirm"."""
    own_items = await list_owned_items(db, current_user.id)
    if payload.kind == "commitment":
        item = Item(
            user_id=current_user.id,
            kind=payload.kind,
            title=payload.title,
            notes=payload.notes,
            is_private=payload.isPrivate,
            start_date=payload.startDate,
            start_time=_parse_time(payload.startTime),
            timezone=str(user_zone(current_user)),
            duration_minutes=payload.durationMinutes,
            recurrence=payload.recurrence,
            recurrence_until=_resolve_recurrence_until(payload),
            weekdays=(
                _weekdays_to_bitmask(payload.weekdays)
                if payload.weekdays is not None
                else None
            ),
        )
        warnings = warnings_for(payload, own_items, payload.startDate)
    else:
        item = Item(
            user_id=current_user.id,
            kind=payload.kind,
            title=payload.title,
            notes=payload.notes,
            is_private=payload.isPrivate,
            due_on=payload.dueOn,
            prep_minutes=payload.prepMinutes,
            prep_lead_days=payload.prepLeadDays,
            reminder_offsets=payload.reminderOffsets,
        )
        warnings = []
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item_to_response(item, warnings)


@router.post("", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: ItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ItemResponse:
    """Create a commitment or deadline; commitments carry overlap warnings."""
    return await _create_item(db, current_user, payload)


@router.post(
    "/confirm", response_model=ItemResponse, status_code=status.HTTP_201_CREATED
)
async def confirm_item(
    payload: ItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ItemResponse:
    """Persist a confirmed draft (same shape and rules as creation)."""
    return await _create_item(db, current_user, payload)


@router.get("", response_model=List[ItemResponse])
async def list_items(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[ItemResponse]:
    """Owner's list, oldest first; private items appear only in detail view."""
    items = await list_owned_items(db, current_user.id)
    return [item_to_response(item) for item in items if not item.is_private]


@router.get("/day")
async def items_for_day(
    target_date: date = Query(..., alias="date"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list:
    """Owner's commitments/deadlines landing on one date (private included)."""
    own_items = await list_owned_items(db, current_user.id)
    commitments: list[dict] = []
    deadlines: list[dict] = []
    for item in own_items:
        kind = getattr(item, "kind", None)
        if kind == "commitment":
            occ = occurrence_on(item, target_date)
            if occ is None:
                continue
            start_minutes = occ[0] * 15
            end_minutes = occ[1] * 15
            commitments.append(
                {
                    "itemId": str(item.id),
                    "kind": "commitment",
                    "title": item.title,
                    "isPrivate": bool(item.is_private),
                    "startTime": (
                        f"{start_minutes // 60:02d}:{start_minutes % 60:02d}"
                    ),
                    "endTime": (
                        f"{end_minutes // 60:02d}:{end_minutes % 60:02d}"
                    ),
                    "date": target_date.isoformat(),
                }
            )
        elif kind == "deadline":
            if getattr(item, "due_on", None) != target_date:
                continue
            deadlines.append(
                {
                    "itemId": str(item.id),
                    "kind": "deadline",
                    "title": item.title,
                    "isPrivate": bool(item.is_private),
                    "dueOn": target_date.isoformat(),
                }
            )
    commitments.sort(key=lambda entry: entry["startTime"])
    return commitments + deadlines


@router.get("/range")
async def items_for_range(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list:
    """Owner's commitments/deadlines landing on each date in [from, to]."""
    if to_date < from_date:
        raise HTTPException(
            status_code=422, detail="to must be on or after from"
        )
    if (to_date - from_date).days > 30:
        raise HTTPException(
            status_code=422, detail="range too large (max 31 days)"
        )
    own_items = await list_owned_items(db, current_user.id)
    entries: list[dict] = []
    day = from_date
    while day <= to_date:
        for item in own_items:
            kind = getattr(item, "kind", None)
            if kind == "commitment":
                occ = occurrence_on(item, day)
                if occ is None:
                    continue
                start_minutes = occ[0] * 15
                end_minutes = occ[1] * 15
                entries.append(
                    {
                        "date": day.isoformat(),
                        "itemId": str(item.id),
                        "kind": "commitment",
                        "title": item.title,
                        "isPrivate": bool(item.is_private),
                        "startTime": (
                            f"{start_minutes // 60:02d}:{start_minutes % 60:02d}"
                        ),
                        "endTime": (
                            f"{end_minutes // 60:02d}:{end_minutes % 60:02d}"
                        ),
                        "warnings": warnings_for(item, own_items, day),
                    }
                )
            elif kind == "deadline":
                if getattr(item, "due_on", None) != day:
                    continue
                entries.append(
                    {
                        "date": day.isoformat(),
                        "itemId": str(item.id),
                        "kind": "deadline",
                        "title": item.title,
                        "isPrivate": bool(item.is_private),
                        "dueOn": day.isoformat(),
                        "warnings": [],
                    }
                )
        day += timedelta(days=1)
    entries.sort(key=lambda entry: (entry["date"], entry.get("startTime") or "99:99"))
    return entries


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ItemResponse:
    """Owner detail (private included) or 404."""
    item = await get_owned_item(db, current_user.id, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item_to_response(item)


_FIELD_MAP = {
    "title": "title",
    "notes": "notes",
    "isPrivate": "is_private",
    "startDate": "start_date",
    "startTime": "start_time",
    "durationMinutes": "duration_minutes",
    "recurrence": "recurrence",
    "recurrenceUntil": "recurrence_until",
    "weekdays": "weekdays",
    "dueOn": "due_on",
    "prepMinutes": "prep_minutes",
    "prepLeadDays": "prep_lead_days",
    "reminderOffsets": "reminder_offsets",
}


@router.put("/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: UUID,
    payload: ItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ItemResponse:
    """Owner-only partial update (kind cannot change); 404 when foreign."""
    item = await get_owned_item(db, current_user.id, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    provided = payload.model_fields_set
    for name in provided:
        if name == "runDays":
            continue
        column = _FIELD_MAP.get(name, name)
        if not hasattr(item, column):
            continue
        value = getattr(payload, name)
        if name == "startTime" and value is not None:
            value = _parse_time(value)
        elif name == "weekdays" and value is not None:
            value = _weekdays_to_bitmask(value)
        setattr(item, column, value)
    if "runDays" in provided and payload.runDays is not None:
        base = payload.startDate or item.start_date
        if base is not None:
            item.recurrence_until = base + timedelta(days=payload.runDays - 1)
    await db.commit()
    await db.refresh(item)
    return item_to_response(item)


@router.delete("/{item_id}")
async def delete_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Owner-only delete; 404 when foreign."""
    item = await get_owned_item(db, current_user.id, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.delete(item)
    await db.commit()
    return {"deleted": True}


def _solution_minutes(solution) -> dict:
    """Total scheduled minutes per behaviour in a solution."""
    totals = {}
    for sched in solution.schedule_items:
        totals[sched.behavior_id] = (
            totals.get(sched.behavior_id, 0) + sched.scheduled_duration
        )
    return totals


@router.post("/preview")
async def preview_item(
    draft: ItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """What would this draft cost the day? Two solves, nothing written.

    Deadlines do not occupy time: displaced/dropped are empty and so are
    warnings. A day with no plannable problem yields empty displaced/dropped
    with warnings still computed.
    """
    if draft.kind != "commitment":
        return {"displaced": [], "dropped": [], "warnings": []}
    own_items = await list_owned_items(db, current_user.id)
    warnings = warnings_for(draft, own_items, draft.startDate)
    try:
        problem, _raw_weights = await _load_problem(db, current_user, draft.startDate)
    except HTTPException:
        return {"displaced": [], "dropped": [], "warnings": warnings}

    occ = occurrence_on(draft, draft.startDate)
    draft_periods = set(range(occ[0], occ[1])) if occ is not None else set()
    solver = CandidateSolver()
    timeout = settings.OPTIMIZATION_TIMEOUT_SECONDS
    try:
        baseline = await run_in_solver_pool(
            solver.solve, problem, uuid4(), timeout_seconds=timeout
        )
        blocked_problem = dataclasses.replace(
            problem,
            blocked_periods=frozenset(
                set(problem.blocked_periods) | draft_periods
            ),
        )
        blocked = await run_in_solver_pool(
            solver.solve, blocked_problem, uuid4(), timeout_seconds=timeout
        )
    except SolverBusyError as exc:
        logger.info("Solver pool busy during preview: %s", exc.detail)
        raise HTTPException(
            status_code=503,
            detail=exc.detail,
            headers={"Retry-After": "2"},
        )
    except (InfeasibleProblemError, UnboundedProblemError, SolverTimeoutError,
            SolverError) as exc:
        logger.info("Preview solve produced no plan: %s", exc.detail)
        raise HTTPException(status_code=422, detail=exc.detail)

    baseline_minutes = _solution_minutes(baseline)
    blocked_minutes = _solution_minutes(blocked)
    by_id = {b.id: b for b in problem.behaviors}
    displaced = [
        {
            "behaviorId": str(behavior_id),
            "behaviorName": (
                by_id[behavior_id].name if behavior_id in by_id else "?"
            ),
            "minutes": minutes - blocked_minutes.get(behavior_id, 0),
        }
        for behavior_id, minutes in baseline_minutes.items()
        if minutes > blocked_minutes.get(behavior_id, 0)
    ]
    dropped = [
        {
            "behaviorId": str(behavior_id),
            "behaviorName": (
                by_id[behavior_id].name if behavior_id in by_id else "?"
            ),
            "minutes": minutes,
        }
        for behavior_id, minutes in baseline_minutes.items()
        if minutes > 0 and blocked_minutes.get(behavior_id, 0) == 0
    ]
    return {"displaced": displaced, "dropped": dropped, "warnings": warnings}
