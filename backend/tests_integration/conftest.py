import asyncio
import os
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.database import Base, get_db

# Use in-memory SQLite for tests
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(autouse=True)
async def init_test_db():
    """Initialize test database."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a clean database session for a test."""
    async with TestingSessionLocal() as session:
        yield session
        # Clear data after each test to ensure isolation
        # For SQLite in-memory, we might need a different strategy if we want real isolation
        # But for now, let's keep it simple.
        await session.rollback()

@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Test client with database dependency override."""
    async def _get_test_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_test_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def auth_client(client: AsyncClient) -> AsyncClient:
    """Test client with authentication header."""
    email = "authuser@example.com"
    password = "Password123"
    
    # Register
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "name": "Auth User",
            "password": password
        }
    )
    
    # Login
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password
        }
    )
    token = response.json()["accessToken"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
