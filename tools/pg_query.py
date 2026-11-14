"""Run SQL against the database in DATABASE_URL and print rows as psql -tA would.

Exists so tools/migration_cycle.sh does not depend on a psql client or on a
container name, and works the same on a laptop and in CI.

    python tools/pg_query.py "select 1"      # query, prints tab-separated rows
    python tools/pg_query.py - < seed.sql    # script, executes statement by statement
"""
import asyncio
import os
import re
import sys

import asyncpg


def _dsn() -> str:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        sys.exit("DATABASE_URL is not set")
    return dsn.replace("postgresql+asyncpg://", "postgresql://")


async def _run(sql: str, script: bool) -> None:
    conn = await asyncpg.connect(_dsn())
    try:
        if script:
            for statement in (s.strip() for s in re.split(r";\s*\n", sql)):
                if statement:
                    await conn.execute(statement)
            return
        rows = await conn.fetch(sql)
    finally:
        await conn.close()

    def render(value: object) -> str:
        if value is None:
            return ""
        # asyncpg returns PostgreSQL's "char" type as bytes ('r', 'c').
        if isinstance(value, (bytes, bytearray)):
            return value.decode()
        return str(value)

    lines = ["\t".join(render(v) for v in row.values()) for row in rows]
    if lines:
        sys.stdout.write("\n".join(lines) + "\n")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: pg_query.py '<sql>' | pg_query.py - < script.sql")
    if sys.argv[1] == "-":
        asyncio.run(_run(sys.stdin.read(), script=True))
    else:
        asyncio.run(_run(sys.argv[1], script=False))


if __name__ == "__main__":
    main()
