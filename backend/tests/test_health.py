"""Health endpoint must actually touch the database."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app


@pytest.mark.asyncio
async def test_health_reports_connected_when_the_database_answers(monkeypatch):
    """A real query runs: this uses an in-memory database, not the configured one."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr("app.main.async_session_maker", session_factory)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    await engine.dispose()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["database"] == "connected"


@pytest.mark.asyncio
async def test_health_returns_503_when_the_database_is_unreachable(monkeypatch):
    """If the check never queried the database, this would still report healthy."""

    class _BrokenSession:
        async def __aenter__(self):
            raise RuntimeError("connection refused")

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr("app.main.async_session_maker", lambda: _BrokenSession())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unhealthy"
    assert body["database"] == "unavailable"


@pytest.mark.asyncio
async def test_root_still_answers():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "version" in response.json()
