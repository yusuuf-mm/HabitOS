"""Contract test: UI time slot labels must not diverge from backend canonical definitions."""

from __future__ import annotations

from pathlib import Path

from app.core.constants import get_time_slot_definitions


def test_time_slot_definitions_canonical():
    defs = get_time_slot_definitions()
    assert [d["key"] for d in defs] == [
        "early_morning",
        "morning",
        "midday",
        "afternoon",
        "evening",
        "night",
        "flexible",
    ]
    assert [d["label"] for d in defs] == [
        "Early morning (05:00-07:00)",
        "Morning (07:00-12:00)",
        "Midday (12:00-14:00)",
        "Afternoon (14:00-17:00)",
        "Evening (17:00-21:00)",
        "Night (21:00-24:00)",
        "Flexible (05:00-24:00)",
    ]
    assert [(d["start"], d["end"]) for d in defs] == [
        ("05:00", "07:00"),
        ("07:00", "12:00"),
        ("12:00", "14:00"),
        ("14:00", "17:00"),
        ("17:00", "21:00"),
        ("21:00", "24:00"),
        ("05:00", "24:00"),
    ]


def test_frontend_behavior_form_derives_time_slot_labels_from_backend():
    """Frontend must not hardcode divergent time slot labels; it derives them from the backend endpoint."""
    root = Path(__file__).resolve().parents[2]
    form_path = root / "frontend" / "src" / "components" / "BehaviorForm.tsx"
    content = form_path.read_text(encoding="utf-8")
    # Must not contain the old hardcoded label table.
    assert "Early Morning (4-8 AM)" not in content
    assert "Morning (8 AM-12 PM)" not in content
    assert "Midday (12-4 PM)" not in content
    assert "Afternoon (4-8 PM)" not in content
    assert "Evening (8 PM-12 AM)" not in content
    # Must derive from backend-served definitions.
    assert "/behaviors/time-slots" in content or "time-slots" in content
    assert "TIME_SLOTS" not in content or "TimeSlotDef" in content or "slotDefinitions" in content
