"""Live Supabase smoke: register, login, create, solve, week preview.

Run from ``backend/`` with a Supabase ``DATABASE_URL`` in the environment:

    uv run python scripts/supabase_smoke.py

No token is printed. The script creates a fresh throwaway user on each run.
"""
import asyncio
import logging
import sys
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


async def main() -> None:
    email = f"smoke+{uuid4().hex[:8]}@example.com"
    password = "SmokePass123"
    today = date.today()
    solve_date = today + timedelta(days=1)
    week_start = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
    checks: list[bool] = []

    def record(name: str, response: httpx.Response, expected: int) -> bool:
        ok = response.status_code == expected
        checks.append(ok)
        print(f"{name}: HTTP {response.status_code} {'OK' if ok else 'FAIL'}")
        if not ok:
            print(f"  body: {response.text[:500]}")
        return ok

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://habit-os-smoke"
        ) as client:
            if not record("health", await client.get("/api/health"), 200):
                return

            registered = await client.post(
                "/api/v1/auth/register",
                json={"email": email, "name": "Supabase Smoke", "password": password},
            )
            if not record("register", registered, 200):
                return
            token = registered.json()["accessToken"]
            user_id = registered.json()["user"]["id"]
            print(f"  user_id={user_id}")

            logged_in = await client.post(
                "/api/v1/auth/login", json={"email": email, "password": password}
            )
            if not record("login", logged_in, 200):
                return
            print(f"  login_user_matches={logged_in.json()['user']['id'] == user_id}")

            headers = {"Authorization": f"Bearer {token}"}
            objectives = await client.get(
                "/api/v1/behaviors/objectives", headers=headers
            )
            if not record("objectives", objectives, 200):
                return
            available = objectives.json()["data"]
            if not available:
                print("  FAIL: registration created no default objectives")
                return
            print(f"  objective_count={len(available)}")

            created = await client.post(
                "/api/v1/behaviors",
                headers=headers,
                json={
                    "name": "Supabase smoke focus block",
                    "description": "Created by the Supabase smoke test",
                    "category": "productivity",
                    "energyCost": 5,
                    "durationMin": 30,
                    "durationMax": 60,
                    "preferredTimeSlots": ["flexible"],
                    "objectiveImpacts": [
                        {"objectiveId": available[0]["id"], "impactScore": 0.5}
                    ],
                    "isActive": True,
                    "isProtected": False,
                },
            )
            if not record("create_behavior", created, 201):
                return
            print(f"  behavior_id={created.json()['data']['id']}")

            solved = await client.post(
                "/api/v1/optimization/solve",
                headers=headers,
                json={"targetDate": solve_date.isoformat(), "maxExecutionTimeMs": 30000},
            )
            if not record("solve", solved, 200):
                return
            run = solved.json()["data"]["run"]
            print(
                f"  run_id={run['id']} status={run['status']} "
                f"scheduled={len(run.get('scheduledBehaviors', []))} "
                f"total_score={run.get('totalScore')}"
            )

            previewed = await client.post(
                "/api/v1/optimization/week/preview",
                headers=headers,
                json={"weekStart": week_start.isoformat()},
            )
            if not record("week_preview", previewed, 200):
                return
            preview = previewed.json()["data"]
            unavailable = sum(1 for day in preview["days"] if not day["available"])
            print(
                f"  week_start={preview['weekStart']} days={len(preview['days'])} "
                f"unavailable={unavailable} skipped={len(preview['skippedDays'])}"
            )

    print(
        f"SMOKE_RESULT {'PASS' if checks and all(checks) else 'FAIL'} "
        f"({sum(checks)}/{len(checks)} checks)"
    )


if __name__ == "__main__":
    asyncio.run(main())
