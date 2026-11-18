"""Shared ownership helpers + commitment expansion (docs/ITEMS.md).

One place decides what "the user's item" means and how a commitment occupies
time, so the items router, the optimizer and the preview endpoint cannot drift
apart. Nothing here decides visibility: privacy is a read-path concern, while
every commitment — private included — still blocks solver time.
"""

from datetime import date, datetime, time as dtime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import Item


def _field(obj: object, *names: str, default=None):
    """Read the first present attribute among alias names (Item vs ItemCreate)."""
    for name in names:
        if isinstance(obj, dict):
            if name in obj and obj[name] is not None:
                return obj[name]
        elif hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value
    return default


def _start_time_parts(value) -> Optional[tuple[int, int]]:
    """(hour, minute) from a time object or an "HH:MM" string."""
    if value is None:
        return None
    if isinstance(value, dtime):
        return (value.hour, value.minute)
    if isinstance(value, str):
        try:
            parsed = datetime.strptime(value.strip(), "%H:%M")
            return (parsed.hour, parsed.minute)
        except ValueError:
            return None
    return None


def _owner_id(user_or_id) -> UUID:
    """Accept a User row or a raw user id (the optimizer passes the user)."""
    return getattr(user_or_id, "id", user_or_id)


async def get_owned_item(
    db: AsyncSession, user_id, item_id: UUID
) -> Optional[Item]:
    """THE shared ownership helper: the user's item, or None (missing/foreign)."""
    result = await db.execute(
        select(Item).where((Item.id == item_id) & (Item.user_id == _owner_id(user_id)))
    )
    return result.scalars().first()


async def list_owned_items(db: AsyncSession, user_id) -> list[Item]:
    """All of the user's items, oldest first."""
    result = await db.execute(
        select(Item)
        .where(Item.user_id == _owner_id(user_id))
        .order_by(Item.created_at)
    )
    return list(result.scalars().all())


def occurrence_on(item: object, day: date) -> Optional[tuple[int, int]]:
    """(start_period, end_period) of a commitment on a date, or None.

    Commitments only: deadlines have no duration and never occupy time.
    Periods derive from the stored LOCAL start_time; item.timezone is a
    snapshot kept for display and does not shift periods.
    """
    if _field(item, "kind") != "commitment":
        return None
    start_date = _field(item, "start_date", "startDate")
    if start_date is None or day < start_date:
        return None
    recurrence = _field(item, "recurrence")
    end = _field(item, "recurrence_until", "recurrenceUntil") or start_date
    if day > end:
        return None
    if recurrence == "once":
        if day != start_date:
            return None
    elif recurrence == "daily":
        pass
    elif recurrence == "weekdays":
        if day.weekday() >= 5:
            return None
    elif recurrence == "weekly":
        if day.weekday() != start_date.weekday():
            return None
    elif recurrence is None:
        return None
    else:
        return None

    parts = _start_time_parts(_field(item, "start_time", "startTime"))
    duration = _field(item, "duration_minutes", "durationMinutes")
    if parts is None or duration is None:
        return None
    start_minutes = parts[0] * 60 + parts[1]
    start_period = start_minutes // 15
    end_period = (start_minutes + int(duration) + 14) // 15
    return (start_period, end_period)


async def blocked_periods_for_day(
    db: AsyncSession,
    user_id,
    day: date,
    exclude_item_id: Optional[UUID] = None,
) -> set[int]:
    """Union of periods occupied by the user's commitments on a date.

    Private items are included: privacy is visibility, not solver behaviour.
    """
    items = await list_owned_items(db, user_id)
    blocked: set[int] = set()
    for item in items:
        if exclude_item_id is not None and item.id == exclude_item_id:
            continue
        occ = occurrence_on(item, day)
        if occ is None:
            continue
        blocked.update(range(occ[0], occ[1]))
    return blocked


def warnings_for(fields: object, own_items: list, day: date) -> list[str]:
    """Overlap + sleep-window warnings for a commitment draft. Deadlines: []."""
    if _field(fields, "kind") != "commitment":
        return []
    warnings: list[str] = []
    mine = occurrence_on(fields, day)
    if mine is None:
        return []
    own_id = _field(fields, "id")
    for other in own_items or []:
        if own_id is not None and _field(other, "id") == own_id:
            continue
        occ = occurrence_on(other, day)
        if occ is None:
            continue
        if max(mine[0], occ[0]) < min(mine[1], occ[1]):
            title = _field(other, "title", default="?")
            warnings.append(f"overlaps commitment '{title}' on {day.isoformat()}")
    if mine[0] < 20 or mine[1] > 84:
        warnings.append("falls in the sleep window (21:00-05:00)")
    return warnings


def item_to_response(item: Item, warnings: Optional[list[str]] = None):
    """Map an Item row to its API shape (startTime "HH:MM", weekdays list)."""
    from app.schemas.item import ItemResponse

    start_time = item.start_time
    if isinstance(start_time, dtime):
        start_time = start_time.strftime("%H:%M")
    bitmask = item.weekdays
    weekdays = None
    if isinstance(bitmask, int) and not isinstance(bitmask, bool):
        weekdays = [i for i in range(7) if bitmask & (1 << i)]
    elif bitmask is not None:
        weekdays = list(bitmask)
    return ItemResponse(
        id=item.id,
        kind=item.kind,
        title=item.title,
        notes=item.notes,
        is_private=item.is_private,
        start_date=item.start_date,
        start_time=start_time,
        timezone=item.timezone,
        duration_minutes=item.duration_minutes,
        recurrence=item.recurrence,
        recurrence_until=item.recurrence_until,
        weekdays=weekdays,
        due_on=item.due_on,
        prep_minutes=item.prep_minutes,
        prep_lead_days=item.prep_lead_days,
        reminder_offsets=item.reminder_offsets,
        warnings=list(warnings or []),
        created_at=item.created_at,
    )
