"""Alembic migration environment configuration."""
from logging.config import fileConfig
import asyncio

from sqlalchemy import engine_from_config
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from alembic import context

from app.db.database import Base
from app.core.config import settings

# This is the Alembic Config object
config = context.config

# Set sqlalchemy.url from environment
config.set_main_option("sqlalchemy.url", str(settings.DATABASE_URL))

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the target_metadata
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    is_sqlite = url.startswith("sqlite") if url else False
    
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=is_sqlite,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Run migrations with async support."""
    is_sqlite = connection.engine.url.drivername.startswith("sqlite")
    context.configure(
        connection=connection, 
        target_metadata=target_metadata,
        render_as_batch=is_sqlite,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = create_async_engine(
        str(settings.DATABASE_URL),
        poolclass=NullPool,
    )

    async with connectable.begin() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
