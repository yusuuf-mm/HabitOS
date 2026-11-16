"""Shared test clock helpers.

Integration tests that exercise a route's idea of "today" must ask the same
clock the app asks, not the wall clock: the suite freezes that clock in
``conftest`` so results do not depend on when the suite runs.
"""

from datetime import date, datetime, timezone

from app.core.clock import now_utc


def plan_now() -> datetime:
    """The (frozen) instant the app sees as now."""
    return now_utc()


def plan_day() -> date:
    """The plan-local day the routes treat as today (UTC in tests)."""
    return now_utc().astimezone(timezone.utc).date()
