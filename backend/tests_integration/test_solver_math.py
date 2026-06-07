"""Mathematical verification tests for the MILP solver.

Validates the combinatorial correctness of the 96-period binary formulation.
"""
import pytest
from httpx import AsyncClient
from app.core.constants import PERIODS_PER_DAY, MINUTES_PER_PERIOD


def _time_to_period(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return (int(h) * 60 + int(m)) // MINUTES_PER_PERIOD


def _check_no_overlaps(items: list[dict]) -> None:
    occupied: set[int] = set()
    for item in items:
        n_blocks = item["scheduledDuration"] // MINUTES_PER_PERIOD
        blocks = set(range(item["startPeriod"], item["startPeriod"] + n_blocks))
        overlap = occupied & blocks
        assert not overlap, (
            f"Overlap detected: behavior '{item['behaviorName']}' "
            f"periods {item['startPeriod']}–{item['startPeriod'] + n_blocks - 1} "
            f"collide with already occupied periods {sorted(overlap)}"
        )
        occupied.update(blocks)


def _check_preferences_respected(
    items: list[dict], slot_map: dict[str, set[int]]
) -> None:
    for item in items:
        allowed = slot_map.get(item["behaviorName"], set(range(PERIODS_PER_DAY)))
        n_blocks = item["scheduledDuration"] // MINUTES_PER_PERIOD
        for p in range(item["startPeriod"], item["startPeriod"] + n_blocks):
            assert p in allowed, (
                f"Behavior '{item['behaviorName']}' scheduled at period {p} "
                f"which is outside its allowed periods {sorted(allowed)}"
            )


@pytest.fixture
def slot_map() -> dict[str, set[int]]:
    return {
        "Morning Run":  set(range(0, 32)),    # early_morning + morning
        "Deep Work":    set(range(32, 64)),   # midday + afternoon
        "Evening Read": set(range(64, 80)),   # evening
    }


@pytest.mark.asyncio
async def test_three_behavior_no_overlaps(
    auth_client: AsyncClient,
    slot_map: dict[str, set[int]],
) -> None:
    """3 behaviors, 3 disjoint time windows → solver produces
    zero overlaps and strictly respects preferences."""
    # Fetch pre-seeded objective IDs (created during registration)
    obj_resp = await auth_client.get("/api/v1/behaviors/objectives")
    assert obj_resp.status_code == 200
    by_name = {obj["name"]: obj["id"] for obj in obj_resp.json()["data"]}

    behaviors = [
        {
            "name": "Morning Run",
            "category": "health",
            "durationMin": 30,
            "durationMax": 60,
            "energyCost": 3,
            "objectiveImpacts": [
                {"objectiveId": by_name["health"], "impactScore": 0.8},
                {"objectiveId": by_name["productivity"], "impactScore": 0.2},
                {"objectiveId": by_name["learning"], "impactScore": 0.1},
            ],
            "preferredTimeSlots": ["early_morning", "morning"],
        },
        {
            "name": "Deep Work",
            "category": "productivity",
            "durationMin": 60,
            "durationMax": 180,
            "energyCost": 5,
            "objectiveImpacts": [
                {"objectiveId": by_name["productivity"], "impactScore": 0.9},
                {"objectiveId": by_name["health"], "impactScore": 0.1},
                {"objectiveId": by_name["learning"], "impactScore": 0.3},
            ],
            "preferredTimeSlots": ["midday", "afternoon"],
        },
        {
            "name": "Evening Read",
            "category": "learning",
            "durationMin": 15,
            "durationMax": 45,
            "energyCost": 1,
            "objectiveImpacts": [
                {"objectiveId": by_name["learning"], "impactScore": 0.7},
                {"objectiveId": by_name["wellness"], "impactScore": 0.3},
            ],
            "preferredTimeSlots": ["evening"],
        },
    ]

    for b in behaviors:
        resp = await auth_client.post("/api/v1/behaviors", json=b)
        assert resp.status_code == 201, f"Create {b['name']} failed: {resp.text}"

    # Solve
    resp = await auth_client.post(
        "/api/v1/optimization/solve",
        json={"targetDate": "2026-06-08", "maxExecutionTimeMs": 30000},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True

    run = data["data"]["run"]
    schedule = data["data"]["schedule"]
    assert run["status"] == "completed", f"Run status: {run['status']}"
    assert run["solverStatus"] in ("optimal", "feasible"), (
        f"Solver status: {run['solverStatus']}"
    )

    raw_items = []
    for sb in schedule.get("scheduledBehaviors", []):
        raw_items.append({
            "behaviorName": sb["behavior"]["name"],
            "startPeriod": _time_to_period(sb["startTime"]),
            "scheduledDuration": sb["duration"],
        })

    assert len(raw_items) > 0, "Solver returned an empty schedule"
    _check_no_overlaps(raw_items)
    _check_preferences_respected(raw_items, slot_map)
