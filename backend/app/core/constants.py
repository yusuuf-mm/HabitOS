"""Architectural scheduling constants and helpers."""

MINUTES_PER_PERIOD: int = 15
PERIODS_PER_DAY: int = 96  # 24 * 60 / 15

# Map TimeSlot enum values to contiguous period ranges (0-95).
# Each slot covers a 4-hour block of the 24-hour day.
TIME_SLOT_RANGES: dict[str, tuple[int, int]] = {
    "early_morning": (0, 16),       # 00:00 – 04:00
    "morning":       (16, 32),      # 04:00 – 08:00
    "midday":        (32, 48),      # 08:00 – 12:00
    "afternoon":     (48, 64),      # 12:00 – 16:00
    "evening":       (64, 80),      # 16:00 – 20:00
    "night":         (80, 96),      # 20:00 – 24:00
    "flexible":      (0, 96),       # entire day
}


def period_to_time(period: int) -> str:
    """Convert a 0-based 15-minute period index to ``HH:mm``."""
    total_minutes = period * MINUTES_PER_PERIOD
    day_minutes = total_minutes % (24 * 60)
    h = day_minutes // 60
    m = day_minutes % 60
    return f"{h:02d}:{m:02d}"


def periods_in_time_slot(slot_name: str) -> range:
    """Return the range of period indices belonging to a named time slot."""
    lo, hi = TIME_SLOT_RANGES.get(slot_name, (0, 96))
    return range(lo, hi)
