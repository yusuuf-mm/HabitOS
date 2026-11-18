"""Item routes: commitments, deadlines, privacy and solver blocking (part C)."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.item import Item
from app.models.user import User
from app.services.items import blocked_periods_for_day, occurrence_on
from tests_integration.support import plan_day


async def _behavior(
    client: AsyncClient,
    name: str,
    *,
    slots: list[str],
    lo: int,
    hi: int,
) -> str:
    response = await client.post(
        "/api/v1/behaviors",
        json={
            "name": name,
            "category": "health",
            "durationMin": lo,
            "durationMax": hi,
            "preferredTimeSlots": slots,
            "isProtected": False,
        },
    )
    assert response.status_code in (200, 201), response.text
    return response.json()["data"]["id"]


async def _user_by_email(db_session: AsyncSession, email: str) -> User:
    result = await db_session.execute(select(User).where(User.email == email))
    return result.scalars().first()


async def _make_user_b(db_session: AsyncSession) -> tuple[User, str]:
    """A second active user plus a bearer token for them."""
    user = User(
        email="userb@example.com",
        username="userb@example.com",
        password_hash="not-a-real-hash",
        status="active",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user, create_access_token({"sub": str(user.id)})


async def _as_user_b(client: AsyncClient, token_b: str, calls):
    """Run *calls* with user B's token, restoring user A's header afterwards."""
    original = client.headers.get("Authorization")
    client.headers["Authorization"] = f"Bearer {token_b}"
    try:
        return await calls()
    finally:
        if original is None:
            client.headers.pop("Authorization", None)
        else:
            client.headers["Authorization"] = original


async def test_commitment_crud_and_warnings(auth_client: AsyncClient):
    tomorrow = plan_day() + timedelta(days=1)
    created = await auth_client.post(
        "/api/v1/items",
        json={
            "kind": "commitment",
            "title": "Late call",
            "startDate": tomorrow.isoformat(),
            "startTime": "22:00",
            "durationMinutes": 60,
            "recurrence": "once",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert any("sleep window" in w for w in body["warnings"]), body["warnings"]
    item_id = body["id"]

    listed = await auth_client.get("/api/v1/items")
    assert listed.status_code == 200, listed.text
    assert any(item["id"] == item_id for item in listed.json())

    detail = await auth_client.get(f"/api/v1/items/{item_id}")
    assert detail.status_code == 200, detail.text

    updated = await auth_client.put(
        f"/api/v1/items/{item_id}", json={"title": "Late call v2"}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "Late call v2"

    deleted = await auth_client.delete(f"/api/v1/items/{item_id}")
    assert deleted.status_code == 200, deleted.text

    gone = await auth_client.get(f"/api/v1/items/{item_id}")
    assert gone.status_code == 404, gone.text


async def test_cross_user_gets_404_not_403(
    auth_client: AsyncClient, db_session: AsyncSession
):
    tomorrow = plan_day() + timedelta(days=1)
    created = await auth_client.post(
        "/api/v1/items",
        json={
            "kind": "commitment",
            "title": "Mine",
            "startDate": tomorrow.isoformat(),
            "startTime": "09:00",
            "durationMinutes": 60,
            "recurrence": "once",
        },
    )
    assert created.status_code == 201, created.text
    item_id = created.json()["id"]

    _, token_b = await _make_user_b(db_session)

    async def probe():
        results = []
        results.append(await auth_client.get(f"/api/v1/items/{item_id}"))
        results.append(
            await auth_client.put(f"/api/v1/items/{item_id}", json={"title": "hijack"})
        )
        results.append(await auth_client.delete(f"/api/v1/items/{item_id}"))
        blist = await auth_client.get("/api/v1/items")
        return results, blist

    results, blist = await _as_user_b(auth_client, token_b, probe)
    for response in results:
        assert response.status_code == 404, response.text
    assert blist.status_code == 200, blist.text
    assert all(item["id"] != item_id for item in blist.json())


async def test_preview_displaces_and_persists_nothing(
    auth_client: AsyncClient, db_session: AsyncSession
):
    behavior_id = await _behavior(
        auth_client, "Morning run", slots=["morning"], lo=60, hi=60
    )
    tomorrow = plan_day() + timedelta(days=1)
    preview = await auth_client.post(
        "/api/v1/items/preview",
        json={
            "kind": "commitment",
            "title": "Dentist",
            "startDate": tomorrow.isoformat(),
            "startTime": "07:00",
            "durationMinutes": 300,
            "recurrence": "once",
        },
    )
    assert preview.status_code == 200, preview.text
    data = preview.json()
    named = {d.get("behaviorId") for d in data["displaced"]} | {
        d.get("behaviorId") for d in data["dropped"]
    }
    assert behavior_id in named, data

    listed = await auth_client.get("/api/v1/items")
    assert listed.status_code == 200, listed.text
    assert listed.json() == []

    user = await _user_by_email(db_session, "authuser@example.com")
    result = await db_session.execute(
        select(Item).where(Item.user_id == user.id)
    )
    assert list(result.scalars().all()) == []


async def test_confirm_creates(auth_client: AsyncClient):
    tomorrow = plan_day() + timedelta(days=1)
    confirmed = await auth_client.post(
        "/api/v1/items/confirm",
        json={"kind": "deadline", "title": "File taxes", "dueOn": tomorrow.isoformat()},
    )
    assert confirmed.status_code == 201, confirmed.text
    item_id = confirmed.json()["id"]

    listed = await auth_client.get("/api/v1/items")
    assert listed.status_code == 200, listed.text
    assert any(item["id"] == item_id for item in listed.json())


async def test_private_item_hidden_from_list_but_in_detail_and_still_blocks(
    auth_client: AsyncClient, db_session: AsyncSession
):
    day = plan_day() + timedelta(days=1)
    confirmed = await auth_client.post(
        "/api/v1/items/confirm",
        json={
            "kind": "commitment",
            "title": "Secret",
            "isPrivate": True,
            "startDate": day.isoformat(),
            "startTime": "08:00",
            "durationMinutes": 60,
            "recurrence": "once",
        },
    )
    assert confirmed.status_code == 201, confirmed.text
    item_id = confirmed.json()["id"]

    listed = await auth_client.get("/api/v1/items")
    assert listed.status_code == 200, listed.text
    assert all(item["id"] != item_id for item in listed.json())

    detail = await auth_client.get(f"/api/v1/items/{item_id}")
    assert detail.status_code == 200, detail.text

    user = await _user_by_email(db_session, "authuser@example.com")
    blocked = await blocked_periods_for_day(db_session, user.id, day)
    assert 32 in blocked, sorted(blocked)


async def test_recurrence_expires_by_date_and_timezone_snapshot(
    auth_client: AsyncClient, db_session: AsyncSession
):
    start = plan_day() + timedelta(days=1)
    created = await auth_client.post(
        "/api/v1/items",
        json={
            "kind": "commitment",
            "title": "Standup",
            "startDate": start.isoformat(),
            "startTime": "08:00",
            "durationMinutes": 60,
            "recurrence": "daily",
            "runDays": 3,
        },
    )
    assert created.status_code == 201, created.text
    created_body = created.json()
    item_id = created_body["id"]

    user = await _user_by_email(db_session, "authuser@example.com")
    result = await db_session.execute(
        select(Item).where(
            (Item.user_id == user.id) & (Item.id == UUID(item_id))
        )
    )
    item = result.scalars().first()
    assert item is not None

    assert occurrence_on(item, plan_day() + timedelta(days=1)) is not None
    assert occurrence_on(item, plan_day() + timedelta(days=3)) is not None
    assert occurrence_on(item, plan_day() + timedelta(days=4)) is None

    user.timezone = "Asia/Tokyo"
    await db_session.commit()

    detail = await auth_client.get(f"/api/v1/items/{item_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["timezone"] == created_body["timezone"]

    await db_session.refresh(item)
    occ = occurrence_on(item, plan_day() + timedelta(days=1))
    assert occ is not None and occ[0] == 32, occ


async def test_invalid_kind_combinations_are_422(auth_client: AsyncClient):
    tomorrow = (plan_day() + timedelta(days=1)).isoformat()

    deadline_with_start = await auth_client.post(
        "/api/v1/items",
        json={"kind": "deadline", "title": "x", "dueOn": tomorrow, "startDate": tomorrow},
    )
    assert deadline_with_start.status_code == 422, deadline_with_start.text

    commitment_missing_duration = await auth_client.post(
        "/api/v1/items",
        json={
            "kind": "commitment",
            "title": "x",
            "startDate": tomorrow,
            "startTime": "08:00",
            "recurrence": "once",
        },
    )
    assert commitment_missing_duration.status_code == 422, commitment_missing_duration.text

    bad_start_time = await auth_client.post(
        "/api/v1/items",
        json={
            "kind": "commitment",
            "title": "x",
            "startDate": tomorrow,
            "startTime": "08:10",
            "durationMinutes": 60,
            "recurrence": "once",
        },
    )
    assert bad_start_time.status_code == 422, bad_start_time.text
