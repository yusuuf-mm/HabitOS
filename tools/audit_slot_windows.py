"""One-off, read-only audit: behaviours that violate the new contiguous-window
duration validation, taken from the live DB and from seed_data.py's config.

Run: uv run python ../scratch/audit_slot_windows.py
"""

from __future__ import annotations

import ast
import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
sys.path.insert(0, BACKEND)

from app.core.constants import longest_contiguous_minutes_for_time_slots  # noqa: E402


def slot_key(name: str) -> str:
    return str(name).split(".")[-1].lower()


def violations(name, min_d, max_d, slots):
    longest = longest_contiguous_minutes_for_time_slots(slots)
    problems = []
    if max_d < min_d:
        problems.append("durationMax < durationMin")
    if min_d > longest:
        problems.append(f"min {min_d} > longest contiguous run {longest}")
    if max_d > longest:
        problems.append(f"max {max_d} > longest contiguous run {longest}")
    return longest, problems


def seed_configs():
    path = os.path.join(BACKEND, "scripts", "seed_data.py")
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            getattr(t, "id", None) == "behavior_configs" for t in node.targets
        ):
            rows = []
            for elt in node.value.elts:
                values = []
                for value_node in elt.elts:
                    if isinstance(value_node, ast.Constant):
                        values.append(value_node.value)
                    elif isinstance(value_node, ast.List):
                        values.append([slot_key(ast.unparse(e)) for e in value_node.elts])
                    else:
                        values.append(slot_key(ast.unparse(value_node)))
                rows.append(values)
            # (name, description, category, min_d, typical_d, max_d, energy, slots, impacts)
            return [(r[0], r[3], r[5], r[7]) for r in rows if len(r) >= 9]
    return []


async def db_behaviors():
    from sqlalchemy import select

    from app.db.database import async_session_maker
    from app.models import Behavior

    async with async_session_maker() as session:
        result = await session.execute(select(Behavior))
        return [
            (
                b.name,
                b.min_duration,
                b.max_duration,
                [slot_key(s.value if hasattr(s, "value") else s) for s in b.preferred_time_slots],
                b.is_active,
            )
            for b in result.scalars().all()
        ]


def report(label, rows, has_active=False):
    print(f"\n== {label} ==")
    total = 0
    for row in rows:
        if has_active:
            name, min_d, max_d, slots, is_active = row
            status = f" (is_active={is_active})"
        else:
            name, min_d, max_d, slots = row
            status = ""
        longest, problems = violations(name, min_d, max_d, slots)
        if problems:
            total += 1
            print(f"  VIOLATION {name}{status}: min={min_d} max={max_d} slots={slots}")
            print(f"            longest contiguous={longest} min -> {'; '.join(problems)}")
    if total == 0:
        print("  no violations")
    else:
        print(f"  {total} violating behaviour(s)")
    return total


def main():
    total = report("seed_data.py behaviour_configs", seed_configs())
    try:
        rows = asyncio.run(db_behaviors())
    except Exception as exc:  # DB may be unreachable in this environment
        print(f"\n== database behaviours ==\n  skipped: {type(exc).__name__}: {str(exc)[:200]}")
    else:
        total += report("database behaviours", rows, has_active=True)
    print(f"\nTOTAL VIOLATIONS: {total}")


if __name__ == "__main__":
    main()
