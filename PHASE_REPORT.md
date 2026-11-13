# Planner v2 — phase report

Branch: `feat/planner-v2`. Every commit listed here had the full backend and
frontend suites run before it was made.

---

## Phase 0 — Housekeeping

**Changed**

- Local `main` fast-forwarded to the merge of PR #1 (`a5729d8`).
- Old branch `chore/hosting-migration` deleted locally and on the origin.
- Created `feat/planner-v2` from `main`.

**Real output**

```
## main...origin/main
?? scratch/
```
Untracked `scratch/` holds the one-off benchmark and migration scripts from the
previous session. It is deliberately not committed.

**Unclear / notes**

- `scratch/` is not ignored by `.gitignore`; the tree will show it as untracked
  until it is either committed or ignored. It is not part of any commit here.

---

## Phase 1 — Honest foundation

### 1. One objective definition

`backend/app/optimization/objective.py` is now the only place an objective value
is computed. It sums `weight x impact x scheduled minutes` over the emitted
sessions. Both `solve()` and `solve_partial_day()` share one formulation
(`LinearSolver._solve`) and both report the value from that module, so the old
`/ MINUTES_PER_PERIOD` scaling in the full-day path is gone. That path used to
report 41.65 where the partial path reported 624.75 for the same schedule.

Tests (`backend/tests/test_solver_contract.py`):

- `test_full_and_partial_solve_report_the_same_objective` — same problem, both
  paths, equal values.
- `test_objective_value_matches_the_schedule_it_reports` — the reported value is
  recomputed from the schedule; contributions sum to it.
- `test_objective_units_are_minutes_not_periods` — a 60-minute session scores 60,
  not 4.

### 2. Solver result contract

`backend/app/optimization/status.py` defines `SolveStatus`
(`optimal`, `feasible`, `infeasible`, `protected_conflict`, `unbounded`, `error`)
and `validate_schedule()`: integrality, block alignment, no overlap, windows,
duration bounds, time budget.

Behaviour:

- Optimal → a plan.
- Infeasible / unbounded → `422` with an explanation, no run stored, previous
  plan untouched (route maps the domain exceptions).
- Time limit or any non-optimal status → `SolverTimeoutError` by default: no plan.
  With `accept_nonoptimal=True` the assignment matrix must be integral within
  `1e-6` and pass `validate_schedule()` first, otherwise `SolverError`.
- Unexpected exceptions → `422` for solver errors, `500` with the generic
  "Optimization failed" text. Internal exception text is no longer returned.
- The dead `except TimeoutError` branch is removed (PuLP never raises it).

Tests:

- `test_not_solved_never_becomes_a_plan` — a solver that reports `Not Solved` and
  leaves fractional values raises; no plan is produced.
- `test_not_solved_with_acceptance_still_needs_integral_values` — even with
  acceptance enabled, the relaxation is rejected.
- `test_validation_rejects_overlaps_and_out_of_window_sessions`,
  `test_validation_accepts_a_valid_schedule`, `test_time_budget_is_checked_by_validation`,
  `test_infeasible_problem_raises_instead_of_returning_a_plan`.

`PROTECTED_CONFLICT` exists in the contract but nothing emits it yet: protected
tiers arrive in Phase 3.

### 3. Real health check

`GET /api/health` opens a session and runs `SELECT 1`; a failure returns `503`
with `status: unhealthy`, `database: unavailable`.

Tests (`backend/tests/test_health.py`): success path against an in-memory
database, failure path with a session factory that raises, and the root endpoint.

### 4. Energy claims and AI claims

- Backend: the mock `energyUsage` series is gone from `analytics.py` and the
  schema; `totalEnergySpent` is gone from `DailySchedule` and both endpoints.
  `energy_cost` stays as a dormant column and still round-trips on behaviours, so
  existing rows are untouched.
- Frontend: the "Energy Budget" card, the energy slider in the behaviour form and
  the "Energy: n/10" row are removed; the matching types are deleted. The form
  still submits the dormant default (5) so create/update keep working.
- Claims: README title, tagline, table of contents, the whole "AI-Assisted
  Development" section, the acknowledgements line and the footer are rewritten to
  "a constraint-based daily planner with partial-day re-optimization". The FastAPI
  app description says the same. The GitHub repository description was changed to
  that sentence.

**Real output**

```
backend:  59 passed, 1 skipped, 1 xpassed, 1 warning in 68.41s
frontend: 4 test files passed, 7 tests passed, exit 0
frontend: npx tsc --noEmit  exit 0, no output
frontend: npm run build     exit 0, "✓ built in 40.61s"
```

(`1 skipped` is the Postgres RESTRICT test, which needs `TEST_POSTGRES_URL`.)

**CI on this phase (run 43497791412, workflow_dispatch on `feat/planner-v2`)**

First attempt was red in `Backend Unit Tests` and `Backend Migrations`, on a test
of mine rather than on the product code:

```
tests/test_solver_contract.py::test_objective_units_are_minutes_not_periods FAILED
E       ValueError: too many values to unpack (expected 1)
```

That assertion expected exactly one 60-minute session. The block model has no
contiguity constraint, so CBC on Linux split the 60 minutes into two sessions
where the Windows build emitted one. The test now asserts the total scheduled
minutes (the actual contract) and says in a comment why only the total is
assertable until Phase 3. That is also a direct argument for the Phase 3
candidate-placement formulation.

**Second CI run (43499015502) — green**

```
Backend Unit Tests          success
Backend Integration Tests   success
Backend Migrations          success
Frontend Tests              success
CI/CD Summary               success
```

Local re-run on the same tree: `59 passed, 1 skipped, 1 xpassed in 19.58s`.

### 5. Solves off the event loop

`backend/app/optimization/executor.py` runs solves in a `ThreadPoolExecutor` with
`max_workers=2` and wraps the await in `asyncio.wait_for(solver_limit + 5s)`;
a timeout becomes `SolverTimeoutError`. `POST /optimization/solve` and the
partial-day re-plan both use it. The pool is shut down in the app lifespan.

**Unclear / notes**

- The MCP server (`app/mcp/server.py`) still calls the solver synchronously. It is
  not an HTTP request path, so it was left alone this phase.
- Removing energy from the API changes the response shape; the frontend was
  updated in the same commit, but any external client written against
  `totalEnergySpent` / `energyUsage` will see the fields disappear.
- `GRADING_CHECKLIST.md` and `docs/README_UPGRADE_SUMMARY.md` still describe the
  old AI framing. They are self-assessment documents, not product documentation,
  and were not rewritten. Say if they should be.

---

## Phase 1.5 — Small hardening

### 1. Time limit, and a pool that says "busy"

CBC was already receiving the limit (`PULP_CBC_CMD(timeLimit=self.timeout_seconds)`);
a test now patches the command factory and asserts the value arrives, so a
regression cannot silently drop it and leave CBC running past the await.

The previous pool *queued*: a third request waited behind two solves until its own
`wait_for` fired. It now admits at most `MAX_SOLVER_WORKERS` (2) solves and refuses
the rest immediately with `SolverBusyError` (503, `Retry-After: 2`,
"2 of 2 solver workers are in use; retry in a moment"). Workers are daemon threads
so a stuck CBC cannot keep the process alive. Admission uses a `threading.Lock`,
not an asyncio one: a lock cached from a closed event loop deadlocked the next
loop, which is what made a full suite take 46 minutes once.

Tests: `backend/tests/test_executor.py` (CBC limit, third-solve refusal,
timeout releases the slot) and route-level `backend/tests_integration/test_solve_errors.py`
(422 for infeasible/timeout/unbounded with an explanation and no stored run,
503 for busy with the header, 500 for an unexpected failure without internal text).

### 1a. A real freezing bug found by the new validation

While running the suite, `POST /schedule/reoptimize` failed with
`Solver produced a schedule that fails validation: Exercise: 120 min above max_duration 60`.
Cause: frozen periods were pinned with `LpVariable(..., lowBound=val, upBound=val,
cat="Binary")`, and PuLP **resets both bounds for `cat="Binary"`**. Freezing had
never worked: elapsed sessions were free to move and the day could be over-filled.
They are now pinned with explicit `x == val` constraints, and the re-plan route
builds one problem entry per behaviour instead of one per scheduled row.

### 2. `tools/`

Benchmarks, `migration_cycle.sh`, `audit_slot_windows.py` and the seven timeout
probes moved out of `scratch/` into `tools/` with `tools/README.md`. Secret scan:
no real credentials. One throwaway `user:password@localhost:55433` pair for a
disposable Postgres container (now overridable via `BENCH_DATABASE_URL`), no
machine-specific absolute paths, no tokens. `scratch/` is now in `.gitignore`;
logs and the one-off edit scripts were **not** committed.

### 3. Archive

`GRADING_CHECKLIST.md` and `docs/README_UPGRADE_SUMMARY.md` moved to `docs/archive/`
with a one-line "describes an earlier state of the project" note. Contents otherwise
untouched.

### 4. Repository description

`gh repo edit yusuuf-mm/HabitOS --description "A constraint-based daily planner with
partial-day re-optimization"` changed exactly one field: the repo description. No
other repository settings, branches, secrets or webhooks were touched.

**Real output**

```
backend:  67 passed, 1 skipped, 1 xpassed in 50.21s
frontend: 4 files, 7 tests passed, exit 0
frontend: npx tsc --noEmit exit 0
```

## Phase 2 — Sessions you can count

### The metric, written down first

`docs/METRIC.md` (v1) defines the rate per **session**, against a baseline set `C`
frozen once per day — at an explicit commit, or at 05:00 plan-local time if the
user never commits. `completion_rate = completed / (|C| - released)`;
`released` leaves and is always shown next to the rate; `dropped_by_system` stays
in the denominator and is reported separately; re-planning can reclassify a session
but never shrink `C`. `|C| - released == 0` reports `null`, not `1.0`.

`docs/SESSION_SCHEMA.md` is the smallest schema that makes that computable. No
`plans` table, no per-revision JSON — those stay deferred in `PART_B_DESIGN.md §6`
until multi-day plans, per-session editing or "show me that day exactly" exist.

### What the schema change does

| table | column | why |
|---|---|---|
| `scheduled_behaviors` | `planned_session_id` (uuid, unique) | one session has one identity, across re-plans and inside a completion |
| | `plan_revision` (int, default 1) | which revision of the day produced it |
| | `retired_revision` (int, null) | set when a later revision drops it (system drop) |
| | `released_at` (timestamptz, null) | the user declined it; this is what removes it from the denominator |
| `completion_logs` | `planned_session_id` (fk, null) | a completion now points at one session, not merely a behaviour |
| `optimization_runs` | `plan_revision`, `committed_at`, `baseline_revision` | which revision the day's baseline came from, recorded once |

State is derived from those facts (`completed` / `released_by_user` /
`dropped_by_system` / `missed`), so no status enum can disagree with the
timestamps it duplicates. Re-planning now stamps the new run and its sessions with
`plan_revision = previous + 1`.

Migration `f2a3b4c5d6e7` is additive and backfills in place: every existing
session gets a fresh id, and each old completion is linked to the earliest session
of that behaviour **in its own run**. Two completions for the same behaviour in
the same run cannot both be linked (there is one earliest session), so the extras
stay `NULL` rather than being pointed at a session they may not have completed.
The downgrade drops only the added columns, constraints and index; seeded rows
survive.

### Proof, with real seeded rows on Postgres 15

`tools/migration_cycle.sh` (extended; run against a local `postgres:15-alpine`
container, `docker run --pull never`, port 55433) seeds one user, behaviour, run,
session and completion at revision `b96cd1f49448`, then walks the whole chain and
checks it at each step:

```
== STEP 3: upgrade head ==
  PASS  revision = f2a3b4c5d6e7
  PASS  history rows survive upgrade = 1/1/1
  PASS  every session got a planned_session_id = 1
  PASS  session plan_revision defaults to 1 = 1
  PASS  run plan_revision defaults to 1 = 1
  PASS  legacy completion linked to its session = 1
  PASS  retired/released start empty = 0
== STEP 7: downgrade the session snapshot revision ==
  PASS  revision = e1f2a3b4c5d6
  PASS  history rows survive snapshot downgrade = 1/1/1
  PASS  snapshot columns dropped = 0
  PASS  session id uniqueness constraint dropped = 0
  PASS  completion FK dropped = 0
== STEP 8: upgrade head again (re-backfill) ==
  PASS  revision = f2a3b4c5d6e7
  PASS  history rows survive second snapshot upgrade = 1/1/1
  PASS  session ids re-created = 1
  PASS  completion re-linked = 1
RESULT: ALL CHECKS PASSED
```

42 checks passed across the full chain (including the earlier `c1a2b3c4d5e6` and
`e1f2a3b4c5d6` revisions, which still downgrade and re-upgrade cleanly), and
`alembic check` on the upgraded database reports **"No new upgrade operations
detected"** — the models and the migration agree, which is what CI's drift job
tests.

### Real output

```
backend:  67 passed, 1 skipped, 1 xpassed
frontend: 7 tests passed (4 files)
frontend: npx tsc --noEmit exit 0
frontend: npm run build exit 0 (built in 19.48s)
```

### Uncertainties

- `retired_revision` and `released_at` are written by **no endpoint yet**: the
  columns exist and are backfilled, but there is no release or retire route, so
  every session currently derives to `completed` or `missed`. That is consistent
  (nothing produces a wrong number) but the metric is not yet fully computable —
  it needs the release/retire endpoints and the metric query from the next step.
- `plan_revision` is stored on both the run and its sessions; nothing enforces
  that they agree. A re-plan writes both from the same value.
- The backfill links at most one completion per (run, behaviour). A day that
  genuinely completed two sessions of the same behaviour before this change will
  show one linked session; the older data cannot say which, so it is left
  unlinked rather than guessed.

## Phase 3 — The planner itself

Not started.

## Phase 4 — Re-planning that works

Not started.

---

## Needs a decision

1. **Settled in Phase 1.5:** `scratch/` is ignored and the scripts live in
   `tools/`; the two grading documents are archived in `docs/archive/` with a
   note. Nothing to decide.
2. **Next, if you want the metric to be real:** a release endpoint and a retire
   path are needed before release/retire can be counted. Deferred deliberately —
   they are product surface, not schema.
