# Supabase Postgres

This branch adds Supabase as a managed Postgres option. HabitOS still owns
authentication (custom JWT access/refresh tokens); Supabase Auth, `service_role`
keys and browser-side database writes are deliberately out of scope.

## Project used for the recorded proof

- Project name: `HabitOS`
- Project ref: `znzjilabaxynemuwllwy`
- Region: `us-east-1` (East US / North Virginia, immutable after creation)
- Connection: shared **session pooler**, port `5432`
- Pooler host: `aws-0-us-east-1.pooler.supabase.com` (read from Dashboard → Connect)

The pooler host cannot be derived from the region. Always copy it from the
Dashboard connection dialog. All credentials below are placeholders.

## New machine setup

1. Install the Supabase CLI only if you need to create/link projects
   (`supabase --version` was `3.4.0` for the recorded run). Application runtime
   does not need the CLI.
2. Confirm the project name and region before any create/link operation.
3. Open **Project Settings → Database → Connection strings → Connect → Session
   pooler** and copy the host, user (`postgres.<PROJECT-REF>`) and port.
4. Copy the committed examples and keep the real files ignored:

   ```bash
   cp .env.example .env
   cp backend/.env.example backend/.env
   ```

   Fill `backend/.env` (and the root `.env` if your tooling reads it):

   ```bash
   DATABASE_URL=postgresql+asyncpg://postgres.<PROJECT-REF>:<URL-ENCODED-PASSWORD>@<POOLER-HOST>:5432/postgres
   SUPABASE_URL=https://<PROJECT-REF>.supabase.co
   SUPABASE_ANON_KEY=<anon-key>
   DATABASE_DISABLE_PREPARED_STATEMENTS=False
   ```

   URL-encode the password: `@` becomes `%40`, `%` becomes `%25`, and so on.
   Alembic needs those `%XX` escapes doubled internally; `escape_alembic_url()`
   handles that so a raw URL in `.env` is correct.
5. Set up a fresh database. The seed script deletes existing rows, so do not
   point it at a database you want to keep:

   ```bash
   cd backend
   uv sync
   uv run alembic upgrade head
   uv run alembic check
   uv run python scripts/seed_data.py
   ```

## Transaction pooler caveat

The shared transaction pooler on port `6543` cannot keep prepared statements
across backend connections. If you choose it instead of the session pooler, set:

```bash
DATABASE_DISABLE_PREPARED_STATEMENTS=True
```

and re-run every verification step below. The recorded proof used port `5432`
with this flag `False`; the transaction-pooler variant was **not** exercised.

## Verification

```bash
cd backend
uv run python scripts/supabase_smoke.py
uv run python scripts/supabase_rls_check.py
```

`supabase_smoke.py` registers a throwaway user, logs in, creates a behaviour,
solves a day, previews a week and prints no tokens. `supabase_rls_check.py`
enumerates every `public` table, compares owner row counts with what the anon
key can see through Supabase REST, and prints no key material.

An RLS denial through PostgREST is HTTP `200` with `[]`, not a `401`. That is
expected: the anon key is a valid JWT, and RLS with no policies makes every
table invisible to it. The owner connection used by FastAPI intentionally
bypasses RLS because `FORCE ROW LEVEL SECURITY` is off.

## Secret handling

- `.env` and `backend/.env` are gitignored.
- `.env.example` and `backend/.env.example` contain placeholders only.
- Never log, print or commit the database password or a `service_role` key.
  Rotate any credential that appears in a log or transcript.
- The anon key is designed to be public, but keep it in env config rather than
  source code so projects can be swapped without a code change.
