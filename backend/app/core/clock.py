"""The single clock the app reads "now" from.

Route behaviour depends on the plan-local day (docs/METRIC.md §5): whether a
baseline is frozen, which revision a re-plan creates, whether a re-plan is even
allowed. Reading the wall clock directly made those decisions untestable and made
a handful of tests pass or fail depending on the time of day they ran.

Tests freeze this clock; production never sets it.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone, tzinfo
from typing import Iterator

_now: datetime | None = None


def now_utc() -> datetime:
    """Current time, or the frozen test time when one is set."""
    return _now or datetime.now(timezone.utc)


def today_local(tz: tzinfo) -> date:
    """Today on the plan-local clock for *tz*."""
    return now_utc().astimezone(tz).date()


@contextmanager
def fixed_now(value: datetime) -> Iterator[None]:
    """Freeze :func:`now_utc` for the duration of the block."""
    global _now
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    previous = _now
    _now = value
    try:
        yield
    finally:
        _now = previous
