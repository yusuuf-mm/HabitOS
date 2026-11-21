"""Step 3 model benchmark harness (no product code).

Compares candidate helper models on 10 fixed draft-extraction cases.

    cd backend && uv run python ../tools/bench_helper_models.py
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import statistics
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "backend")))

from app.services import llm  # noqa: E402

TODAY = date(2026, 11, 14)  # a Saturday

SYSTEM_PROMPT = (
    "You extract draft schedule items from the user's message. "
    "Reply with ONLY a JSON array of draft items (no markdown code fences, "
    "no commentary) in this shape, resolving relative dates against today "
    f"({TODAY.isoformat()}, a Saturday): "
    'commitment: {"kind":"commitment","title":str,"startDate":"YYYY-MM-DD",'
    '"startTime":"HH:MM","durationMinutes":int,"recurrence":'
    '"once|daily|weekdays|weekly","runDays":int|null} '
    'deadline: {"kind":"deadline","title":str,"dueOn":"YYYY-MM-DD"} '
    'habit: {"kind":"habit","title":str,"preferredTimeSlots":'
    "[one or more of early_morning|morning|midday|afternoon|evening|night],"
    '"durationMin":int,"durationMax":int} '
    'If essential information is missing or ambiguous, reply {"clarify": '
    '"<question>"} instead of guessing. '
    "When a commitment duration is not stated, you may choose a sensible duration."
)

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SLOTS = {"early_morning", "morning", "midday", "afternoon", "evening", "night"}
_RECURRENCE = {"once", "daily", "weekdays", "weekly"}


def _is_date(value: object) -> bool:
    return isinstance(value, str) and bool(_DATE_RE.match(value))


def _is_hhmm(value: object) -> bool:
    return isinstance(value, str) and bool(_TIME_RE.match(value))


def _is_pos_mult5(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0 and value % 5 == 0


def _check_item(item: object) -> str | None:
    """Return an error string, or None when the item is schema-valid."""
    if not isinstance(item, dict):
        return "item is not an object"
    kind = item.get("kind")
    if kind == "commitment":
        for field in ("title", "startDate", "startTime", "durationMinutes", "recurrence"):
            if field not in item:
                return f"commitment missing {field}"
        if not isinstance(item["title"], str) or not item["title"]:
            return "commitment title must be a non-empty string"
        if not _is_date(item["startDate"]):
            return "commitment startDate must be YYYY-MM-DD"
        if not _is_hhmm(item["startTime"]):
            return "commitment startTime must be HH:MM"
        if not _is_pos_mult5(item["durationMinutes"]):
            return "commitment durationMinutes must be a positive multiple of 5"
        if item["recurrence"] not in _RECURRENCE:
            return "commitment recurrence invalid"
        run_days = item.get("runDays")
        if run_days is not None and (
            not isinstance(run_days, int) or isinstance(run_days, bool) or run_days < 1
        ):
            return "commitment runDays must be a positive int or null"
        return None
    if kind == "deadline":
        for field in ("title", "dueOn"):
            if field not in item:
                return f"deadline missing {field}"
        if not isinstance(item["title"], str) or not item["title"]:
            return "deadline title must be a non-empty string"
        if not _is_date(item["dueOn"]):
            return "deadline dueOn must be YYYY-MM-DD"
        return None
    if kind == "habit":
        for field in ("title", "preferredTimeSlots", "durationMin", "durationMax"):
            if field not in item:
                return f"habit missing {field}"
        if not isinstance(item["title"], str) or not item["title"]:
            return "habit title must be a non-empty string"
        slots = item["preferredTimeSlots"]
        if not isinstance(slots, list) or not slots or any(s not in _SLOTS for s in slots):
            return "habit preferredTimeSlots invalid"
        for field in ("durationMin", "durationMax"):
            if not _is_pos_mult5(item[field]):
                return f"habit {field} must be a positive multiple of 5"
        if item["durationMin"] > item["durationMax"]:
            return "habit durationMin must be <= durationMax"
        return None
    return f"unknown kind {kind!r}"


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _parse_reply(text: str) -> tuple[list | dict | None, str | None]:
    try:
        parsed = json.loads(_strip_fences(text))
    except (json.JSONDecodeError, ValueError) as exc:
        return None, f"invalid JSON: {exc}"
    return parsed, None


def _validate_schema(parsed: list | dict) -> tuple[list | None, str | None]:
    if isinstance(parsed, dict):
        if "clarify" in parsed:
            return None, "clarify"
        return None, "top-level object without clarify is not a list"
    if not isinstance(parsed, list):
        return None, "top-level JSON must be a list"
    for item in parsed:
        error = _check_item(item)
        if error is not None:
            return None, f"schema error: {error}"
    return parsed, None


def _by_kind(items: list, kind: str) -> list:
    return [i for i in items if isinstance(i, dict) and i.get("kind") == kind]


def check_case_1(items: list) -> str | None:
    if len(items) != 3:
        return f"expected exactly 3 items, got {len(items)}"
    deadlines = _by_kind(items, "deadline")
    commitments = _by_kind(items, "commitment")
    habits = _by_kind(items, "habit")
    if len(deadlines) != 1 or len(commitments) != 1 or len(habits) != 1:
        return "expected 1 deadline + 1 commitment + 1 habit"
    if deadlines[0].get("dueOn") != "2026-11-16":
        return f"deadline dueOn {deadlines[0].get('dueOn')!r} != 2026-11-16"
    c = commitments[0]
    if c.get("startTime") != "08:00":
        return f"commitment startTime {c.get('startTime')!r} != 08:00"
    if c.get("recurrence") != "daily" or c.get("runDays") != 3:
        return "commitment must be daily with runDays 3"
    if not _is_pos_mult5(c.get("durationMinutes")):
        return "commitment durationMinutes must be a positive multiple of 5"
    if "evening" not in (habits[0].get("preferredTimeSlots") or []):
        return "habit slots must include evening"
    return None


def check_case_2(items: list) -> str | None:
    if len(items) != 1:
        return f"expected 1 item, got {len(items)}"
    c = items[0]
    if c.get("kind") != "commitment":
        return "expected a commitment"
    for key, want in (
        ("startDate", "2026-11-15"),
        ("startTime", "15:30"),
        ("recurrence", "once"),
    ):
        if c.get(key) != want:
            return f"{key} {c.get(key)!r} != {want!r}"
    if c.get("durationMinutes") != 60:
        return f"durationMinutes {c.get('durationMinutes')!r} != 60"
    return None


def check_case_3(items: list) -> str | None:
    if len(items) != 1:
        return f"expected 1 item, got {len(items)}"
    d = items[0]
    if d.get("kind") != "deadline":
        return "expected a deadline"
    if d.get("dueOn") != "2026-11-20":
        return f"dueOn {d.get('dueOn')!r} != 2026-11-20"
    return None


def check_case_4(items: list) -> str | None:
    if len(items) != 1:
        return f"expected 1 item, got {len(items)}"
    c = items[0]
    if c.get("kind") != "commitment":
        return "expected a commitment"
    for key, want in (
        ("recurrence", "weekdays"),
        ("startDate", "2026-11-16"),
        ("startTime", "07:00"),
    ):
        if c.get(key) != want:
            return f"{key} {c.get(key)!r} != {want!r}"
    if c.get("durationMinutes") != 45:
        return f"durationMinutes {c.get('durationMinutes')!r} != 45"
    return None


def check_case_5(items: list) -> str | None:
    if len(items) != 1:
        return f"expected 1 item, got {len(items)}"
    c = items[0]
    if c.get("kind") != "commitment":
        return "expected a commitment"
    for key, want in (
        ("startDate", "2026-11-15"),
        ("startTime", "18:00"),
        ("recurrence", "once"),
    ):
        if c.get(key) != want:
            return f"{key} {c.get(key)!r} != {want!r}"
    if c.get("durationMinutes") != 30:
        return f"durationMinutes {c.get('durationMinutes')!r} != 30"
    return None


def check_case_6(items: list) -> str | None:
    if len(items) != 1:
        return f"expected 1 item, got {len(items)}"
    h = items[0]
    if h.get("kind") != "habit":
        return "expected a habit"
    if "evening" not in (h.get("preferredTimeSlots") or []):
        return "habit slots must include evening"
    if not (h.get("durationMin", 1) <= 20 <= h.get("durationMax", 0)):
        return "habit range must cover 20 minutes"
    return None


def check_case_7(items: list) -> str | None:
    if len(items) != 1:
        return f"expected 1 item, got {len(items)}"
    c = items[0]
    if c.get("kind") != "commitment":
        return "expected a commitment"
    if c.get("recurrence") != "daily":
        return f"recurrence {c.get('recurrence')!r} != daily"
    if c.get("startTime") != "09:15":
        return f"startTime {c.get('startTime')!r} != 09:15"
    if c.get("durationMinutes") != 15:
        return f"durationMinutes {c.get('durationMinutes')!r} != 15"
    if c.get("runDays") != 14:
        return f"runDays {c.get('runDays')!r} != 14"
    return None


def check_case_8(items: list) -> str | None:
    if len(items) != 1:
        return f"expected 1 item, got {len(items)}"
    c = items[0]
    if c.get("kind") != "commitment":
        return "expected a commitment"
    for key, want in (
        ("recurrence", "weekly"),
        ("startDate", "2026-11-19"),
        ("startTime", "10:00"),
    ):
        if c.get(key) != want:
            return f"{key} {c.get(key)!r} != {want!r}"
    if c.get("durationMinutes") != 60:
        return f"durationMinutes {c.get('durationMinutes')!r} != 60"
    return None


def check_case_9(items: list) -> str | None:
    deadlines = [d for d in _by_kind(items, "deadline") if d.get("dueOn") == "2026-12-01"]
    if not deadlines:
        return "expected at least one deadline dueOn 2026-12-01"
    return None


CASES = [
    {
        "id": 1,
        "transcript": (
            "A deadline on 16 November I mustn't forget; take my father "
            "to the hospital every morning at 8 for 3 days; a new workout at 8 pm."
        ),
        "check": check_case_1,
    },
    {
        "id": 2,
        "transcript": "Remind me: dentist tomorrow at 3:30 in the afternoon, about an hour",
        "check": check_case_2,
    },
    {"id": 3, "transcript": "Submit the board report by Friday", "check": check_case_3},
    {
        "id": 4,
        "transcript": "Gym every weekday morning at 7 for 45 minutes starting Monday",
        "check": check_case_4,
    },
    {
        "id": 5,
        "transcript": "Call mum on Sunday at 6pm, half an hour",
        "check": check_case_5,
    },
    {"id": 6, "transcript": "Read for 20 minutes in the evening", "check": check_case_6},
    {
        "id": 7,
        "transcript": "Team standup every day at 9:15, 15 minutes, for the next 2 weeks",
        "check": check_case_7,
    },
    {
        "id": 8,
        "transcript": "uh dentist?? no wait \u2014 physio, Thursdays 10am, hour, starts next week",
        "check": check_case_8,
    },
    {
        "id": 9,
        "transcript": "Passport renewal deadline December 1st, and book flights before that",
        "check": check_case_9,
    },
    {"id": 10, "transcript": "something in the morning", "check": None},
]


def run_case(text: str, case: dict) -> tuple[bool, str]:
    parsed, error = _parse_reply(text)
    if error is not None:
        return False, error
    if case["id"] == 10:
        if isinstance(parsed, dict) and "clarify" in parsed:
            return True, ""
        if isinstance(parsed, list) and len(parsed) == 0:
            return True, ""
        return False, "expected a clarify object or empty list, got fabricated items"
    items, error = _validate_schema(parsed)
    if error is not None:
        return False, error
    assert items is not None
    failed = case["check"](items)
    if failed is not None:
        return False, failed
    return True, ""


async def bench_model(model: str) -> dict:
    latencies: list[float] = []
    passed = 0
    failures: list[tuple[int, str, str]] = []
    available = True
    calls = 0
    for case in CASES:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": case["transcript"]},
        ]
        try:
            result = await llm.chat(
                messages, model=model, temperature=0.0, max_tokens=800, timeout_seconds=90
            )
        except Exception as exc:  # noqa: BLE001 - record any provider error
            message = str(exc)
            if "HTTP 404" in message:
                available = False
                failures.append((case["id"], "model unavailable (HTTP 404)", ""))
                break
            failures.append((case["id"], f"error: {message[:120]}", ""))
            continue
        calls += 1
        latencies.append(float(result.get("latency_seconds", 0.0)))
        ok, reason = run_case(str(result.get("text", "")), case)
        if ok:
            passed += 1
        else:
            failures.append((case["id"], reason, str(result.get("text", ""))[:200]))
    median = round(statistics.median(latencies), 3) if latencies else 0.0
    return {
        "model": model,
        "available": available,
        "calls": calls,
        "median_latency": median,
        "passed": passed,
        "failures": failures,
    }


async def main() -> None:
    results = []
    for model in llm.candidate_models():
        results.append(await bench_model(model))

    print("| Model | Available | Median latency (s) | Schema+expectation pass |")
    print("| --- | --- | --- | --- |")
    for row in results:
        print(
            f"| {row['model']} | {row['available']} | "
            f"{row['median_latency']:.3f} | {row['passed']}/10 |"
        )
    for row in results:
        for case_id, reason, raw in row["failures"]:
            line = f"FAIL {row['model']} case {case_id}: {reason}"
            if raw:
                line += f" | raw: {raw}"
            print(line)


if __name__ == "__main__":
    asyncio.run(main())
