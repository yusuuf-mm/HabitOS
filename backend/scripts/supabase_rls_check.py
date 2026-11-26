"""Prove every public table is RLS-protected and hidden from the anon key.

Run from ``backend/`` with a Supabase ``DATABASE_URL`` and ``SUPABASE_URL`` /
``SUPABASE_ANON_KEY`` in the environment:

    uv run python scripts/supabase_rls_check.py

The anon key is read from settings and never printed. An RLS denial through
PostgREST is HTTP 200 with an empty array; the owner row count proves the
tables are not empty.
"""
import asyncio
import logging
import sys
from pathlib import Path

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.db.database import engine

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


async def main() -> None:
    async with engine.connect() as conn:
        tables = (
            await conn.execute(
                text(
                    """
                    SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND c.relkind = 'r'
                    ORDER BY c.relname
                    """
                )
            )
        ).all()
        policies = (
            await conn.execute(
                text("SELECT count(*) FROM pg_policies WHERE schemaname = 'public'")
            )
        ).scalar_one()

    print(f"public_tables={len(tables)} policies={policies}")
    print(f"rls_enabled_all={all(bool(row.relrowsecurity) for row in tables)}")
    print(f"force_rls_any={any(bool(row.relforcerowsecurity) for row in tables)}")

    headers = {
        "apikey": settings.SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_ANON_KEY}",
        "Accept": "application/json",
    }
    base = settings.SUPABASE_URL.rstrip("/")
    results: list[bool] = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for name, rls, force_rls in tables:
            async with engine.connect() as conn:
                owner_rows = (
                    await conn.execute(text(f'SELECT count(*) FROM public."{name}"'))
                ).scalar_one()

            response = await client.get(
                f"{base}/rest/v1/{name}", params={"select": "*"}, headers=headers
            )
            body = response.text.strip()
            denied = response.status_code in (401, 403) or body == "[]"
            results.append(denied)
            print(
                f"{name}: HTTP {response.status_code} owner_rows={owner_rows} "
                f"anon_rows={'0' if body == '[]' else 'NONEMPTY'} "
                f"rls={bool(rls)} force={bool(force_rls)} "
                f"-> {'DENIED' if denied else 'READABLE'}"
            )

    print(
        f"ANON_RESULT {'PASS' if results and all(results) else 'FAIL'} "
        f"({sum(results)}/{len(results)} tables denied)"
    )


if __name__ == "__main__":
    asyncio.run(main())
