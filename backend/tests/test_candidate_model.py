"""Contract tests for the candidate-placement prototype (docs/FORMULATION.md).

Deliberately does not assert how CBC splits or orders sessions: it asserts what
the plan promises — one contiguous session per behaviour, durations inside the
behaviour's bounds, no overlaps, frozen periods untouched, declines reported with
reasons. These are the same promises the production model must keep, so they can
move with it unchanged.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from candidate_model import Behavior, MINUTES_PER_PERIOD, solve  # noqa: E402

WEIGHTS = {"health": 1.0}


def _behavior(behavior_id="b1", *, lo=30, hi=60, window=(20, 48), protected=False, sessions=1, gap=0):
    return Behavior(
        id=behavior_id,
        name=f"Behaviour {behavior_id}",
        min_duration=lo,
        max_duration=hi,
        impacts={"health": 1.0},
        windows=[window],
        protected=protected,
        sessions=sessions,
        min_gap=gap,
    )


def _cells(session):
    return set(range(session.start, session.start + session.duration // MINUTES_PER_PERIOD))


def test_one_contiguous_session_per_behaviour():
    result = solve([_behavior(lo=30, hi=60)], WEIGHTS)
    assert result.status == "optimal"
    assert len(result.sessions) == 1
    session = result.sessions[0]
    assert 30 <= session.duration <= 60
    assert session.duration % MINUTES_PER_PERIOD == 0


def test_sessions_never_overlap():
    behaviors = [_behavior(f"b{i}", lo=30, hi=60, window=(20, 40)) for i in range(4)]
    result = solve(behaviors, WEIGHTS)
    occupied: set[int] = set()
    for session in result.sessions:
        cells = _cells(session)
        assert not (cells & occupied), "two sessions share a period"
        occupied |= cells


def test_frozen_periods_are_never_replanned():
    """A session that already ran is not moved, repeated or overwritten."""
    frozen = {period: 1 for period in range(20, 22)}  # 30 minutes already elapsed
    behaviors = [_behavior("b1", lo=30, hi=60, window=(20, 48))]
    result = solve(behaviors, WEIGHTS, frozen=frozen)
    for session in result.sessions:
        assert not (_cells(session) & set(frozen))


def test_behaviour_with_no_remaining_room_is_declined_not_dropped():
    frozen = {period: 1 for period in range(20, 48)}
    result = solve([_behavior("b1", lo=30, hi=60, window=(20, 48))], WEIGHTS, frozen=frozen)
    assert result.sessions == []
    # A flexible behaviour with no free room is "no_fit"; over_capacity is
    # reserved for protected demand that cannot fit (docs/FORMULATION.md).
    assert [(d.behavior_id, d.reason) for d in result.declined] == [("b1", "no_fit")]


def test_protected_behaviours_are_all_scheduled_when_they_fit():
    behaviors = [_behavior(f"b{i}", lo=30, hi=30, window=(20, 40), protected=True) for i in range(3)]
    result = solve(behaviors, WEIGHTS)
    assert result.declined == []
    assert len(result.sessions) == 3


def test_protected_over_capacity_is_reported_with_reasons():
    behaviors = [_behavior(f"b{i}", lo=60, hi=60, window=(20, 26), protected=True) for i in range(5)]
    result = solve(behaviors, WEIGHTS)
    assert result.sessions, "some protected sessions still fit"
    assert result.declined, "the ones that do not fit must be reported"
    for decline in result.declined:
        assert decline.reason in {"over_capacity", "no_fit", "preempted_by_protected"}
        assert decline.reason == "over_capacity", "protected demand never loses to anything else"


def test_multi_session_behaviour_respects_count_and_gap():
    behavior = _behavior("b1", lo=15, hi=15, window=(20, 40), sessions=3, gap=15)
    result = solve([behavior], WEIGHTS)
    assert 1 <= len(result.sessions) <= 3
    ordered = sorted(result.sessions, key=lambda s: s.start)
    for previous, current in zip(ordered, ordered[1:]):
        gap_minutes = (current.start - (previous.start + previous.duration // MINUTES_PER_PERIOD)) * MINUTES_PER_PERIOD
        assert gap_minutes >= 15


def test_objective_is_the_emitted_schedule():
    """The reported value is computed from the sessions, not the LP's own value."""
    result = solve([_behavior(lo=30, hi=30, window=(20, 40))], WEIGHTS)
    expected = sum(session.duration * 1.0 for session in result.sessions)
    assert result.objective == pytest.approx(expected)
