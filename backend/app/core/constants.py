"""Architectural scheduling constants and helpers."""

from __future__ import annotations

MINUTES_PER_PERIOD: int = 15
PERIODS_PER_DAY: int = 96  # 24 * 60 / 15


def _time_to_period(hour: int, minute: int = 0) -> int:
    return (hour * 60 + minute) // MINUTES_PER_PERIOD


# Canonical time windows (single source of truth for backend + frontend labels).
# Each entry: key -> (label, start_period, end_period) where end is exclusive.
TIME_SLOT_DEFINITIONS: list[dict[str, object]] = [
    {"key": "early_morning", "label": "Early morning (05:00-07:00)", "start": "05:00", "end": "07:00"},
    {"key": "morning", "label": "Morning (07:00-12:00)", "start": "07:00", "end": "12:00"},
    {"key": "midday", "label": "Midday (12:00-14:00)", "start": "12:00", "end": "14:00"},
    {"key": "afternoon", "label": "Afternoon (14:00-17:00)", "start": "14:00", "end": "17:00"},
    {"key": "evening", "label": "Evening (17:00-21:00)", "start": "17:00", "end": "21:00"},
    {"key": "night", "label": "Night (21:00-24:00)", "start": "21:00", "end": "24:00"},
    {"key": "flexible", "label": "Flexible (05:00-24:00)", "start": "05:00", "end": "24:00"},
]


def _parse_hhmm(value: str) -> tuple[int, int]:
    hour_s, minute_s = value.split(":", 1)
    hour = int(hour_s)
    minute = int(minute_s)
    if hour == 24 and minute == 0:
        return 24, 0
    return hour, minute


def _slot_range(start: str, end: str) -> tuple[int, int]:
    sh, sm = _parse_hhmm(start)
    eh, em = _parse_hhmm(end)
    start_p = _time_to_period(sh % 24, sm)
    end_p = PERIODS_PER_DAY if (eh == 24 and em == 0) else _time_to_period(eh, em)
    return (start_p, end_p)


# Map TimeSlot enum values to contiguous period ranges (0-95), derived from canonical definitions.
TIME_SLOT_RANGES: dict[str, tuple[int, int]] = {
    str(d["key"]): _slot_range(str(d["start"]), str(d["end"])) for d in TIME_SLOT_DEFINITIONS
}

TIME_SLOT_LABELS: dict[str, str] = {str(d["key"]): str(d["label"]) for d in TIME_SLOT_DEFINITIONS}


def get_time_slot_definitions() -> list[dict[str, object]]:
    """Return canonical time slot definitions for clients (single source of truth)."""
    return [dict(d) for d in TIME_SLOT_DEFINITIONS]


def period_to_time(period: int) -> str:
    """Convert a 0-based 15-minute period index to ``HH:mm``."""
    total_minutes = period * MINUTES_PER_PERIOD
    day_minutes = total_minutes % (24 * 60)
    h = day_minutes // 60
    m = day_minutes % 60
    return f"{h:02d}:{m:02d}"


def periods_in_time_slot(slot_name: str) -> range:
    """Return the range of period indices belonging to a named time slot."""
    lo, hi = TIME_SLOT_RANGES.get(slot_name, (0, PERIODS_PER_DAY))
    return range(lo, hi)


def periods_for_time_slots(slot_names: list[str] | None) -> set[int]:
    """Return the union of period indices allowed by slot_names (empty/None => all day)."""
    if not slot_names:
        return set(range(PERIODS_PER_DAY))
    allowed: set[int] = set()
    for name in slot_names:
        lo, hi = TIME_SLOT_RANGES.get(name, (0, PERIODS_PER_DAY))
        allowed.update(range(lo, hi))
    return allowed


def allowed_minutes_for_time_slots(slot_names: list[str] | None) -> int:
    """Total minutes covered by the union of selected windows."""
    return len(periods_for_time_slots(slot_names)) * MINUTES_PER_PERIOD
