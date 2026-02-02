"""Database initialization and management."""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Engine configuration
engine_kwargs = {
    "echo": settings.DEBUG,
}

if not str(settings.DATABASE_URL).startswith("sqlite"):
    engine_kwargs.update({
        "pool_size": settings.DATABASE_POOL_SIZE,
        "max_overflow": settings.DATABASE_MAX_OVERFLOW,
        "pool_pre_ping": settings.DATABASE_POOL_PRE_PING,
    })
else:
    from sqlalchemy.pool import StaticPool
    engine_kwargs["poolclass"] = StaticPool
    engine_kwargs["connect_args"] = {"check_same_thread": False}

if settings.TESTING and not str(settings.DATABASE_URL).startswith("sqlite"):
    engine_kwargs["poolclass"] = NullPool

# Create async engine
engine = create_async_engine(
    str(settings.DATABASE_URL),
    **engine_kwargs
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for dependency injection."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database on startup."""
    # Import models to register them
    from app.models import (  # noqa: F401
        User,
        Behavior,
        Objective,
        Constraint,
        OptimizationRun,
        CompletionLog,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connection on shutdown."""
    await engine.dispose()


# Import Base for metadata
from sqlalchemy.orm import declarative_base

Base = declarative_base()
