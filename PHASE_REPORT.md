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

### Identity is now tested, not just migrated

`backend/tests_integration/test_session_identity.py` drives the real routes:

- `test_replan_increments_plan_revision_on_run_and_sessions` — seeds revision 1,
  calls `POST /api/v1/schedule/reoptimize`, then reads the database: the old run
  is revision **1**, the new run is **2**, every session of the new run carries
  **2**, and every `planned_session_id` in the day is non-null and distinct.
- `test_completion_can_point_at_one_session` — the same behaviour scheduled twice
  gets two different session ids; a completion naming the second resolves back to
  exactly that session and not the first, which is the join `docs/METRIC.md` needs.

### The cycle also runs in CI

`tools/migration_cycle.sh` used `docker exec … psql` and assumed uv, so it could
only run on one machine. It now reads `BENCH_DATABASE_URL` or `DATABASE_URL`, uses
`tools/pg_query.py` (asyncpg) instead of a `psql` client, and picks `uv run` only
where uv exists. CI's **Backend Migrations** job runs it first, on the empty
service database, followed by the existing upgrade/downgrade/drift steps.

Locally, after the refactor: **41 checks passed**, `RESULT: ALL CHECKS PASSED`.

### Real output

```
backend:  69 passed, 1 skipped, 1 xpassed in 29.30s
backend:  tests_integration/test_session_identity.py: 2 passed in 3.20s
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

## Phase 2.5 — Making the metric real

### The definition first, amended in place

`docs/METRIC.md` v1 was amended before any code used it: the baseline stays open
until the later of the first session starting or 05:00 plan-local; runs before
that are drafts, not re-plans, and create no dropped sessions. The known-tension
section says plainly that a re-plan can only lower the strict rate, that the UI
shows `completion_rate_vs_feasible` beside it, and that the strict rate stays the
headline. Deactivating a behaviour before a session starts is a user release.
Late completions (any time before the local day ends) count and are flagged.
Timezones are stored on `users.timezone` and used for every boundary.
Multi-day rates are summed counts, never averaged percentages.

Because the query and the commit endpoint were written after the amendments in
this same phase, there was nothing to retrofit; the doc, the service and the
tests were written together and agree.

### One module decides the number

`backend/app/services/metrics.py` resolves the day's baseline plan, classifies
each session (`completed` / `released_by_user` / `dropped_by_system` / `missed`)
from timestamps only, and computes:

```
completion_rate             = completed / (|C| - released)
released_ratio              = released / |C|
completion_rate_vs_feasible = completed / (|C| - released - dropped_by_system)
```

`null` whenever the denominator is zero. `compute_range` sums counts across days
(`docs/METRIC.md` §7). The dashboard's `completionRate` now comes from it. The old
query counted every `scheduled_behaviors` row of every run created in the last 7
days, so each re-plan added a whole plan to the denominator — the inflation this
phase was asked to remove.

### Sessions: release, retirement, identity

- `POST /api/v1/schedule/{id}/release` sets `released_at`, but only before the
  session starts (409 afterwards: it can only be missed). Releasing removes it
  from the denominator and reports it beside the rate.
- A re-plan of a **frozen** baseline writes `retired_revision` on every session it
  drops and carries `planned_session_id` forward for every session it keeps, even
  when the session moved. Nothing is deleted or renumbered.
- A re-plan before the baseline freezes is a draft: revision 1, no retirement.
- Deactivating a behaviour releases that behaviour's not-yet-started sessions
  (`docs/METRIC.md` §3.5) instead of dropping them.
- `mark_complete` now records `planned_session_id`, so a completion names one
  session.

**Schema correction found while testing:** global uniqueness on
`planned_session_id` made carrying a session into the next revision impossible
(`UNIQUE constraint failed`). Identity is now unique per
`(planned_session_id, optimization_run_id)`, and the completion FK was dropped
because the same id legitimately exists once per revision. Migration
`b3c4d5e6f7a8` adds `users.timezone` and performs that swap, with a downgrade that
restores the old constraint and FK.

### Several optimization runs on the same day

- **Before the freeze:** every run is a draft at revision 1 and retires nothing.
  `POST /schedule/commit` accepts the latest run (or an explicit `run_id`),
  clearing `baseline_revision` on the others, so exactly one baseline exists per
  day. Committing repeatedly is idempotent while open.
- **After the freeze:** the baseline cannot be re-committed (409). A re-plan
  becomes revision N+1, retires what it drops and keeps the rest's identities.
- A `/optimization/solve` run after the baseline is frozen creates a revision-1
  run that is *not* the baseline; its sessions are excluded from the rate. Only
  `reoptimize` advances a frozen day. (Recorded here so it is a decision, not an
  accident.)

### Tests (contract only)

`backend/tests_integration/test_metric.py` — 12 tests: rate = completed /
(baseline − released); a dropped session stays in the denominator and is reported
separately; zero denominator returns `null` not `1.0`; a late completion counts
and is flagged; a completion after the local day ends does not count; drafts are
`open` until the later of 05:00 or the first session start; multi-day is summed
(1/1 + 1/10 = 2/11); the timezone shifts the day boundary (skipped on machines
without a tz database, e.g. this Windows Python); release removes a session from
the denominator; exactly one baseline per day; a re-plan never shrinks `|C|`; a
carried session keeps its `planned_session_id`.

**Real output**

```
backend:  80 passed, 2 skipped, 1 xpassed in 70.69s
metric + identity: 13 passed, 1 skipped
frontend: 7 tests passed (4 files), tsc --noEmit clean
```

### Frontend

The dashboard card shows the rate with its two small numbers, e.g.
`55%` and `2 released · 3 dropped`, and `—` when the denominator is zero.

### KI-001 (the subset-test hang) — still open

Re-ran the documented reproduction after the daemon-thread pool and `threading.Lock`
change:

```
uv run pytest tests_integration/test_solver_math.py tests_integration/test_behavior_updates.py -q
-> 2 passed in 4.76s, then the process did not exit (killed at 120 s)
```

So the event-loop lock change did **not** fix it; the pool is not the cause. It
stays in `KNOWN_ISSUES.md`, now with this evidence.

### H9 defect status

| Defect | Status |
|---|---|
| Duplicate entries in a re-plan problem | **Fixed** in Phase 1.5 — one problem entry per behaviour. |
| Frozen periods never actually frozen | **Fixed** in Phase 1.5 — pinned by constraints, not `LpVariable` bounds, which PuLP resets for `Binary`. |
| Global cutoff (server clock, whole-plan elapsed) | **Fixed here** — current period is computed in the user's plan-local clock and adjusted by the target date, so a past day is fully elapsed and a future day is fully ahead. |
| Timezone | **Fixed here** — `users.timezone` (IANA, default UTC) drives the day boundary, the 05:00 baseline hour, the local day end for late completions and current-period checks. |

Phase 4 should not redo any of these; what remains for it is the per-session
re-solve behaviour and the release/retire UI.

## Phase 2.5 fix round — solve guard and tzdata

**`POST /optimization/solve` is refused for a frozen today.** If today already has
a baseline (committed, or frozen by 05:00 / the first session), the endpoint
returns `409` with `baseline is set; use re-plan (POST /api/v1/schedule/reoptimize)
instead of generating a new plan.` Future days are unchanged, and a day with no
frozen baseline is unchanged. Tests:
`test_solve_returns_409_when_todays_baseline_is_frozen` and
`test_solve_for_a_future_day_is_unaffected`.

**tzdata is a dependency.** Added with `uv add tzdata` (2026.6) and pinned in
`backend/requirements.txt`, so the timezone test runs instead of skipping on a
machine without a tz database. The metric suite is now **14 passed, 0 skipped**.

## Phase 3 gate — like-for-like, one objective, declines, speed, oracle

### 1. Like-for-like (every behaviour forced in, one session each)

| instance | block | block obj | candidate | cand obj | delta |
|---|---|---|---|---|---|
| 10 fixed narrow | optimal | 75.21 | optimal | 75.21 | 0.0 |
| 10 fixed wide | optimal | 74.16 | optimal | 74.16 | 0.0 |
| 10 variable narrow | optimal | 159.9 | optimal | 159.9 | 0.0 |
| 10 variable wide | optimal | 333.48 | optimal | 333.48 | 0.0 |
| 20 fixed narrow | optimal | 155.94 | optimal | 155.94 | 0.0 |
| 20 fixed wide | optimal | 179.04 | optimal | 179.04 | 0.0 |
| 20 variable narrow | infeasible | — | Infeasible | — | — |
| 20 variable wide | optimal | 624.75 | optimal | 624.75 | 0.0 |
| 40 × 4 cases | mixed | — | refused (cap 25) | — | — |

**Cases where the candidate is higher: 0.** The earlier gap (223.86 vs 159.9) came
from the candidate model being allowed to decline; with declines removed its
feasible region is a subset of the block model's, and the values are identical on
every instance both can solve. The 20-variable-narrow instance is infeasible for
both, so the models agree there too.

### 2. One objective definition

The prototype now reports `objective` = placement value of the emitted sessions
(the `objective.py` definition), and `solver_objective` = the penalised LP value
(decline penalties included) separately. In the five-protected-behaviour test the
plan value is `60.0` while the solver objective is `−39940.0`; the test
`test_solver_objective_is_reported_separately_from_plan_value` asserts they differ
and that only the placement value matches the emitted minutes.

### 3. Declines explained (`tools/decline_analysis.py`)

| case | scheduled | declined | reason | arithmetic |
|---|---|---|---|---|
| 10 variable narrow | 5 | 5 | `no_fit` | the 300-minute morning window is full; no candidate fits the free periods |
| 15 × 60 min, 300 min window | 5 | 10 | `over_capacity` | 300 / 60 = 5 protected sessions fit |
| 12 protected × 45 min, 300 min | 6 | 6 | `over_capacity` | 300 / 45 = 6 fit, the 7th needs 315 min |
| 40 × 45 min, 1140 min | — | — | refused | 40 behaviours exceed the 25 cap |

The audit reports **0 declines with free capacity and positive value**, i.e. no
decline that needs an explanation beyond capacity or a window conflict.

**Bug found and fixed by this gate:** a multi-session behaviour could be both
scheduled and declined at once (the constraint was `selected + z ≤ sessions`).
The oracle caught it in 200/200 multi-session instances; the constraint is now
`selected + z·sessions ≤ sessions` and `selected + z ≥ 1`.

### 4. Speed (cap, duration step, 30-minute starts)

| instance | candidate status | sessions | seconds |
|---|---|---|---|
| 10 fixed narrow | optimal | 10 | 0.14 |
| 10 fixed wide | optimal | 10 | 0.25 |
| 10 variable narrow | optimal | 5 | 0.26 |
| 10 variable wide | optimal | 10 | 0.41 |
| 20 fixed narrow | optimal | 20 | 0.18 |
| 20 fixed wide | optimal | 20 | 0.44 |
| 20 variable narrow | optimal | 6 | 0.33 |
| 20 variable wide | optimal | 19 | 1.61 |
| 25 fixed wide | optimal | 25 | 0.39 |
| 25 variable wide | optimal | 21 | 3.02 |
| 40 × 4 cases | refused | — | — |
| over-capacity × 3 | optimal with declines | 5 / 13 / 6 | 0.24 / — / 0.26 |

Criteria: every instance up to 20 behaviours proves optimality in under 3 s
(max 1.61 s); 21–25 prove optimality within the 30 s limit (max 3.02 s at 25
variable/wide); nothing returns a non-optimal plan (instances above the cap are
refused with a message, never truncated). **PASS.**

The cap is 25 active behaviours per plan, the candidate duration step keeps at
most 8 lengths per behaviour (always including min and max), and starts align to
30 minutes whenever the duration is a multiple of 30.

### 5. Oracle — 1,000 instances

Four behaviours, 12–16 periods, five categories, 200 each:

```
objective matches: 1000/1000
instances with validation violations: 0
  feasible             200/200 (violations 0)
  multi_session_gap    200/200 (violations 0)
  frozen               200/200 (violations 0)
  protected_conflict   200/200 (violations 0)
  over_capacity        200/200 (violations 0)
production validate_schedule: 100/100 clean
```

Both schedules pass `validate_plan` (bounds, windows, overlap, frozen periods,
session count, gap, protected-never-silent). A 100-instance canonical set also
passes the production `validate_schedule`; the 12–16-period instances cannot be
expressed in its named-slot model without distorting them, which is why both
validators are reported.

### Steps 8-11 — shipped

**8. Production formulation replaced behind the same contract.**
`app/optimization/solvers/candidate.py` (`CandidateSolver`) is what every route,
the re-plan and the MCP tool now build. It keeps `solve(problem, run_id) ->
OptimizationSolution`, `solve_partial_day` for frozen periods, the
`validate_schedule` gate before a plan is returned, the shared `objective.py`
value, and the bounded worker pool. The block solver stays as the reference the
gate compared against; nothing builds it. All contract, frozen-period and the
eight candidate tests pass unedited; 13 new production tests in
`tests/test_candidate_solver.py` assert the same promises against the shipped
class, plus the cap, the duration step, the alignment, the forced solve and the
separate `solver_objective`.

Production mapping the prototype did not have: canonical time slots become
contiguous windows, frozen minutes count towards duration bounds and are
re-emitted unchanged, `time_budget` and `frequency` constraints are honoured, and
`validate_schedule` runs on the merged item list. The coarse `solver` column stays
`linear` (it is a pre-existing enum); the formulation is recorded in
`diagnostics.formulation` and `results.solver`.

Two bugs the swap exposed and this commit fixes: re-plan used the server's
`date.today()` instead of the plan-local day, so a re-plan just after midnight
local found no active run; and `optimization_runs` could not store the solver name
(the column is an enum), which is why the formulation is recorded in diagnostics.

**9. Forced include.** `POST /api/v1/optimization/forced-include` takes
`behaviorIds` and a target date, runs a baseline solve and a forced solve on the
same problem, and returns the forced sessions, the displaced sessions with reasons
and minutes, the objective change, the relaxations (displaced, shortened, or
`no_free_window`), and the penalised value for diagnostics. Both solves use the
same worker pool at **lower priority**: a what-if call refuses while it would take
the last worker, so it can never make a real solve wait. Nothing is persisted.

**10. Editable weights.** `GET /api/v1/behaviors/objectives` now returns the
normalised `weight`; `PUT /api/v1/behaviors/objectives/{id}` sets one weight and
renormalises the whole set to sum to 1 (all-zero falls back to an equal split).
`_load_problem` normalises once, and every plan records
`diagnostics.objective_weights = {raw, normalised}` — verified by
`test_plan_records_the_weights_it_used`.

**11. Docs.** `docs/FORMULATION.md` is rewritten for the shipped model: size
limits, sets, the exact constraints (including the `selected + z` pair), the
objective split, weights, decline reasons, forced include, the diagnostics
contract, and the gate evidence. `docs/METRIC.md` is unchanged.

New tests: `tests/test_candidate_solver.py` (13) and
`tests_integration/test_forced_include.py` (5).

## Phase 3 (first half) — prototype, benchmark, oracle

Production is **not** changed: the candidate-placement model lives in
`tools/candidate_model.py`, the benchmark and oracle in `tools/`, and the contract
tests in `backend/tests/test_candidate_model.py` (which imports the prototype from
`tools/`). `solver/linear.py` is still what the API runs.

### Formulation

`docs/FORMULATION.md`: one binary per candidate session instead of one per
(behaviour, period), so a selected session is contiguous by construction.
Protected behaviours are scheduled or declined with a reason (never silently
skipped); flexible ones may be declined with `no_fit`,
`preempted_by_protected` or `over_capacity`; multi-session behaviours use
explicit slots with a minimum gap; frozen periods are excluded from candidate
generation. The objective is computed from the emitted schedule, exactly as
`objective.py` does today.

### Benchmark: candidate model vs the current block model

Same 12 instances as `bench_cbc.py` (10/20/40 behaviours, fixed/variable
durations, narrow/wide windows) plus three over-capacity instances, one machine,
CBC time limit 30 s. `uv run python tools/bench_candidate_v2.py`.

| instance | block status | block obj | blk sess | blk s | cand obj | cand sess | cand s | declined |
|---|---|---|---|---|---|---|---|---|
| 10 fixed narrow | optimal | 75.21 | 10 | 0.47 | 75.21 | 10 | 0.16 | 0 |
| 10 fixed wide | optimal | 74.16 | 10 | 0.35 | 74.16 | 10 | 0.32 | 0 |
| 10 variable narrow | optimal | 159.9 | 19 | 0.38 | 223.86 | 5 | 0.33 | 0 |
| 10 variable wide | optimal | 333.48 | 37 | 0.38 | 333.48 | 10 | 0.80 | 0 |
| 20 fixed narrow | optimal | 155.94 | 20 | 0.59 | 155.94 | 20 | 0.35 | 0 |
| 20 fixed wide | optimal | 179.04 | 20 | 0.64 | 179.04 | 20 | 0.54 | 0 |
| 20 variable narrow | **infeasible** | — | — | 0.60 | 229.89 | 6 | 0.49 | 0 |
| 20 variable wide | optimal | 624.75 | 72 | 0.72 | 633.42 | 19 | 2.45 | 0 |
| 40 fixed narrow | **infeasible** | — | — | 1.14 | 198.09 | 20 | 0.37 | 0 |
| 40 fixed wide | optimal | 318.15 | 40 | 1.21 | 318.15 | 40 | 0.85 | 0 |
| 40 variable narrow | **infeasible** | — | — | 1.02 | 228.75 | 5 | 0.89 | 0 |
| 40 variable wide | **infeasible** | — | — | 1.10 | 781.47 | 21 | **31.5 (limit)** | 0 |
| 15×60 min in a 300 min window | — | — | — | — | −99820 | 5 | 0.34 | 10 (`over_capacity`) |
| 40×45 min in a 1140 min day | — | — | — | — | 570 | 13 | 3.73 | 0 |
| 12 protected ×45 min in 300 min | — | — | — | — | −59838 | 6 | 0.43 | 6 (`over_capacity`) |

What the numbers say:

1. **Fixed-duration instances agree exactly** (75.21, 74.16, 155.94, 179.04,
   318.15) once the old 15× unit bug is gone, which is the correctness check that
   matters most.
2. **Contiguity is structural.** 10 variable behaviours: block model 19 sessions
   (37 wide), candidate model 5–10. 20 variable wide: 72 sessions versus 19.
3. **Speed favours the candidate model on 10 of 12 instances** (0.16–0.89 s versus
   0.35–1.21 s), with two exceptions: 20 variable wide (2.45 s vs 0.72 s) and
   40 variable wide, which **does not finish proving optimality within 30 s**
   (31.5 s wall). That timeout is the main open issue before replacement.
4. **The variable-duration objectives differ** (223.86 vs 159.9; 633.42 vs 624.75;
   781.47 on an instance the block model calls infeasible). This is a modelling
   difference, not a unit bug: the block model constrains minutes *per selected
   block* and pays for whatever CBC emits, while the candidate model chooses one
   session per behaviour and can therefore reach a schedule the block model
   forbids. It needs review, not silent adoption.
5. **Over-capacity is reported, not crashed**: protected demand that cannot fit
   comes back as declines with `over_capacity`, and the objective carries the
   protected penalty (−99820, −59838).

### Oracle

`tools/oracle.py` brute-forces every decline-or-candidate combination on 12
periods × 3 behaviours. `tools/oracle_compare.py` runs 40 random instances across
four categories (feasible, over-capacity, protected conflict, impossible minimum):

```
objective matches: 40/40
identical schedules: 24/40
  feasible             10/10 (identical schedules 2/10)
  over_capacity        10/10 (identical schedules 10/10)
  protected_conflict   10/10 (identical schedules 2/10)
  impossible_minimum   10/10 (identical schedules 10/10)
```

**Disagreements:** none on the objective. 16 of 40 instances pick a different
schedule with the *same* value — ties, broken differently by CBC and by the
oracle's enumeration order — which is expected and is why the contract tests
assert value and structure, never a particular split.

### Contract tests carried over

`backend/tests/test_candidate_model.py` (8 tests) asserts only what the plan
promises: one contiguous session per behaviour inside its duration bounds, no
overlaps, frozen periods never replanned, a behaviour with no room declined and
reported rather than dropped, protected behaviours all scheduled when they fit,
protected over-capacity reported with a reason, multi-session count and gap
respected, and the objective equal to the emitted schedule's value. None of them
depend on how CBC splits or orders sessions, so they apply to the replacement
unchanged.

`8 passed in 2.12s`.

**Stopping here** as instructed: no production formulation change.

## Phase 4 — Re-planning that works

### Step A — verify and tidy

**A.1 protected tier.** Before this phase only `SolveStatus.PROTECTED_CONFLICT`
existed; there was no flag, no tier and no conflict result. It is now real:

- `behaviors.is_protected` (additive, default false, migration
  `a7b8c9d0e1f2`), surfaced as `isProtected` in create/update/response.
- `BehaviorScheduleInput.protected`, loaded by both the solve and re-plan paths.
- The candidate solver gives a declined protected behaviour a
  `PROTECTED_DECLINE_PENALTY` of 1,000,000, so protected habits are placed
  before anything else while the objective still decides among their feasible
  slots.
- If one still cannot be placed, the solution status becomes
  `protected_conflict` and `diagnostics.protected_conflict` carries
  `{unplaced, conflicting, minimalRelaxation}`. Both the solve route and
  `POST /schedule/reoptimize` answer 409 with that payload and persist nothing.

Tests: five protected cases in `backend/tests/test_candidate_solver.py`
(protected placed first, dropped only when impossible, conflict reports the
blocking set, relaxation is minimal, non-protected still declines normally) and
`backend/tests_integration/test_protected.py` (flag round-trip, protected
conflict 409 on solve, 409 on reoptimize with the old plan intact).

**A.2 clock.** `backend/app/core/clock.py` provides `now_utc()`,
`today_local(tz)` and a `fixed_now` context manager. Production code in metrics,
schedule, analytics and telemetry now asks the clock instead of `datetime.now`
or `date.today`; plan-local days go through `local_today(user_zone(...))`.
Six integration modules had wall-clock dependencies (metric, schedule,
behaviors, restrict_postgres, session_identity, phase4_realtime); the
integration conftest now freezes "now" at 2026-06-08 12:00 UTC, with
`tests_integration/support.py` deriving plan dates from it.

**A.3 solver column.** `optimization_runs.solver` can store `candidate`
(new enum value, migration `b8c9d0e1f2a3`, downgrade rebuilds the type and maps
`candidate` to `linear`). Both write paths record `candidate`; the solver
variant stays in results/diagnostics.

**Proven where it could run:** the local Docker daemon was not running, so
`tools/migration_cycle.sh` was not run locally at first. The same script,
extended in this phase to check `is_protected` and the new enum value and to
downgrade through it, runs in the `Backend Migrations` CI job on
`postgres:15-alpine`, followed by `alembic downgrade base`, `upgrade head` and
`alembic check`; that job is green on `c39914a`.

**Local run (follow-up, 2026-11-16):** Docker Desktop was restarted until its
engine answered (`docker desktop restart`; Server 28.2.2), and the existing
`postgres-db` container (`postgres:15-alpine`, local images only, no pulls) was
started. `alembic upgrade head` against `behaviordb` reached
`b8c9d0e1f2a3 (head)` and the app booted against it; locally the migration is
therefore exercised upgrade-side. `tools/migration_cycle.sh` itself was not run
locally; the full downgrade cycle remains the CI job's proof.

### Step B — docs/ITEMS.md

Written: habit / commitment / deadline held in one `items` table with a kind
discriminator and kind-specific nullable columns (recommended over widening
`behaviors`), commitments entering the solver as blocked periods rather than
decision variables, commitments excluded from the completion-rate denominator
and reported separately, limited runs expiring by date range, reminder offsets
as data (no scheduler yet), and the AI helper producing a validated
`items[]` draft that the user confirms.

### Step C — screens

- **Re-plan:** "Re-plan the rest of my day" on the schedule page, followed by a
  plain-language diff (kept / moved to HH:MM / dropped / added) computed from
  the before and after schedules. The diff keys on `plannedSessionId` — see the
  follow-up note below; the row id is per run and cannot be used.
- **Declines:** the schedule payload now carries the run's `declines`; the UI
  turns reason codes into sentences and offers "What would it cost to fit it?",
  wired to `POST /optimization/forced-include`, reporting the displaced
  sessions and the objective change.
- **Release and commit:** per-session Release and "Commit / start my day" call
  the existing endpoints; the dashboard shows "Kept my plan" and "Handled the
  day" with the released/dropped counts, and the invented "+5%" trend is gone.
- **Weights:** an objectives editor on the behaviours page sends normalised
  weights through the existing objectives PUT.
- **Landing hero:** 96 squares now render a real day produced by the candidate
  solver via `tools/generate_hero_day.py` (`npm run gen:hero` →
  `frontend/src/data/heroDay.json`), not `Math.random()`.

Checks: frontend `tsc --noEmit` clean, `npm test` 17 passed (10 new),
`npm run build` succeeds; backend full suite 121 passed, 1 skipped, 1 xpassed.

**Screens:** the landing page was opened in the real browser
(`docs/images/phase4-landing-hero.png`); the hero grid is the generated day.
In the follow-up below the authenticated screens were opened against the local
Postgres run and photographed; component tests cover them in CI as before.

### Follow-up — re-plan session identity, local Postgres run, screens (2026-11-16)

**Re-plan identity.** `ScheduledBehavior.id` is per run, so keying the "What
changed" diff on it reported every session as dropped and re-added. The diff
(`frontend/src/lib/planDiff.ts`) now keys on `plannedSessionId` (falling back to
the row id). The API surface was the missing piece: the schedule GET and the
solve response now expose `plannedSessionId`, and
`backend/tests_integration/test_session_identity.py` pins the contract —
`test_replan_api_keeps_planned_session_id_while_row_ids_change`. A real re-plan
against the local Postgres for `demo@example.com` kept all 7 planned sessions
while every row id changed, with nothing dropped or added and 6 sessions moved;
the browser re-plan for `shots@example.com` showed the same shape in the UI
(5 moved, 1 kept, 1 declined as `over_capacity`).

**Local run.** Backend and frontend ran locally against the existing Docker
`postgres:15-alpine` container (`behaviordb`, migrations at head
`b8c9d0e1f2a3`); backend health reported `database: connected`. Seed users
(`demo@example.com`, `shots@example.com`, `tomorrow@example.com`, password
`DemoPass1`) drove the API and the browser. Solving is by
`POST /optimization/solve` with `targetDate`; `reoptimize` and `commit` operate
on plan-local today only.

**Commit 409 is by design.** `resolve_day_plan` freezes the baseline at
`max(05:00 local, first session start)` (`docs/METRIC.md` §2); the seeded run was
created after that point, so `POST /schedule/commit` correctly returns 409 for
today. The release action was exercised in the browser and returned its
confirmation notice.

**Screens photographed:** `docs/images/phase4-schedule-overview.png`,
`docs/images/phase4-declines.png` (forced-include cost answer visible),
`docs/images/phase4-replan-diff.png` and `docs/images/phase4-weights-editor.png`.

### Audit fixes — misleading optimization-page numbers (2026-11-17)

Four confirmed display findings and one infrastructure failure, fixed in small
commits. The solver itself was not changed.

- **1250% objective progress** (commit `e313323`): the analytics API sent
  `round(weight * 100, 1)` and the panel multiplied by 100 again, so a 0.125
  weight displayed as 1250% under the heading "Objective Progress". The
  backend now sends the normalised 0-1 weight (`normalise_weights`, so the
  shares sum to 1.0) and the frontend renders it once. The schema docstring and
  the new "Objective Weights" heading state what the number is; the per-row
  trend icons remain but are documented as a hardcoded `"stable"`, not a
  measured trend. Verified live after reconnecting the database: the API
  returns `progress: 0.125` for each of the eight objectives.
- **NaN% completion rate** (commit `688dd2a`): the panel divided the summed
  daily completion rates by `behaviorCompletions.length`. With no rows that is
  a division by zero and the header rendered `NaN%`. The average is now `null`
  with no data and the header shows "—", matching the dashboard's convention.
- **Total Score as a percentage** (commit `5b43e3a`): `totalScore` is the
  solver's raw objective value — weighted impact points × minutes, no scaling
  (`objective.py` states the units) — but the run panel and History multiplied
  it by 100 and rendered it as a percentage with a progress bar. It is now
  "Total Objective Value" in `pts·min` with a caption saying it compares
  between runs of the same day and is not a percentage; the normalised
  contributions list below remains the real percentage breakdown.
- **Fake constraints-satisfied count** (commit `5b43e3a`):
  `map_run_to_response` sets both `constraints_satisfied` and
  `constraints_total` to `len(scheduled_behaviors)` with `# Simplified`
  comments, so the panel's "Constraints Satisfied X / Y" could never disagree.
  The panel and History now show "Sessions Scheduled" with the real session
  count (the mapper always fetches the behaviours, including for history). The
  backend fields stay in the API for compatibility but are no longer displayed;
  a real constraint count remains future work.
- **Backend database reconnected** (no commit; gitignored `backend/.env`):
  the old `postgres-db` container published no host port, so the host backend
  fell back to a default `user` role that does not exist (`FATAL: role "user"
  does not exist`) and health reported `database: unavailable` — that, not
  solver code, is why optimization calls failed. The container was recreated
  from the local `postgres:15-alpine` image with `5432` published to the host,
  and `backend/.env` points `DATABASE_URL` at it. Health now reports
  `database: connected`, and a live solve for `demo@example.com` (one behavior,
  "Morning Run") returned `solverStatus: optimal` with a persisted run;
  scheduled 07:30-08:00.

Also re-verified with the backend restarted on the fixed code: analytics
returns `progress` as a 0-1 fraction (0.125 each, sum 1.0) and an empty
`behaviorCompletions` list now maps to the em dash, not NaN%.

---

## Tidy-up pass (2026-11-17)

Small approved follow-ups, each verified before committing. The solver's
placement logic is unchanged except for the stability term below.

- **Stability term.** Re-plans now penalise moving carried sessions:
  `λ = 0.001` per minute shifted from the previous start (distance moved, not
  moved-or-not), LP objective only — the reported plan value is still the
  placement value of the emitted sessions. The re-plan route passes each
  behaviour's earliest not-fully-elapsed session start (in-progress sessions
  count from now) and the disruption is reported in
  `diagnostics.stability` (`carried_sessions`, `minutes_shifted`,
  `penalty_applied`) and in the re-plan response's `disruption`.
  `docs/FORMULATION.md` gained the term and no longer claims there is no
  protected tier; it also records that `optimization_runs.solver` is
  `candidate` now. Tests: a 30-minute shift lands on the closest free start
  instead of dropping the session, with `solver_objective` below the plan
  value by exactly the penalty; a full solve reports no `stability`.
- **Commit-flow integration test.** `test_commit_flow.py` drives one day
  through the real routes — solve (3 sessions) → commit → complete one →
  release one → re-plan (carried 3, shifted 0) → squeeze all three into
  midday → re-plan (drops the lowest-value one) — then asserts
  `(baseline, completed, released, dropped) = (3, 1, 1, 1)`, rate `0.5`,
  `vs_feasible` `1.0`, and the same numbers on the dashboard route.
- **Retire-path fix found by that test.** The re-plan persist loop only
  visited behaviours present in the new plan, so a behaviour declined
  outright never got `retired_revision` and system drops could never count
  through real usage. Missing behaviours' previous sessions are now retired
  too (frozen days only). Nothing is deleted or renumbered.
- **Protected-penalty evidence.** A 20-behaviour crowded day (3 protected,
  ~1,100 min demand over a 05:00–24:00 day, mixed values) solves optimal
  with 18 sessions, 2 `over_capacity` declines, plan value 636.3, all 3
  protected placed. The 1,000,000 penalty is ~1,500× any realistic plan
  value, so the constant stays. Pinned by
  `test_protected_penalty_holds_on_a_realistic_crowded_day`.
- **KI-001 fixed.** See `KNOWN_ISSUES.md`: the shared test engine was never
  disposed and aiosqlite's worker thread is non-daemon, so the process hung
  in `threading._shutdown` after the summary. A session fixture now
  disposes the engine; the documented repro exits in ~6 s.
- **Constraint fields deprecated.** `constraints_satisfied` /
  `constraints_total` (and their `constraintsSatisfied` / `constraintsTotal`
  API names) always carried the session count, never a real evaluation.
  They now return 0, are marked deprecated in the schema, `openapi.yaml`,
  README and frontend types, and stay present so older clients keep
  parsing. The UI already shows "Sessions Scheduled" and declines instead.
- **Mechanical.** Deleted tracked `test_pw.py` (throwaway bcrypt script);
  moved the six Phase 4 PNGs from `screenshots/` to `docs/images/` and
  fixed the report references; stopped the leftover uvicorn workers on
  8001/8002 (backend 8000 kept).

**Real output**

```
backend:  126 passed, 1 skipped, 1 xpassed in 125.81s
frontend: 5 files, 20 tests passed; tsc --noEmit clean; build ok (30.13s)
```

## Step 1 — items backend (commitments and deadlines) (2026-11-18)

Branch `feat/items-and-helper` from `main` (after PR #3 merged). The helper's
storage and solver groundwork, no LLM yet (Step 2/3 later).

- **Schema.** One `items` table, commitments and deadlines **only** (no habit
  rows; the unification cost is recorded in `docs/ITEMS.md`). A `CHECK`
  constraint (`ck_items_kind_fields`) keeps cross-kind states unrepresentable:
  commitments carry local `start_date` + `start_time` + `timezone` snapshot
  (not a timestamptz instant), duration, recurrence, and deadlines carry
  `due_on` (plus optional prep/reminder data). `is_private` flag. Migration
  `c9d0e1f2a3b4` is the new head; `tools/migration_cycle.sh` head expectations
  updated to it.
- **Solver (Wonder's own change).** `OptimizationProblem.blocked_periods`:
  commitment-occupied periods are filtered at candidate generation, so they
  are occupied time, never decision variables. Frozen/re-plan interplay and a
  fully blocked behaviour (declines `no_fit`, never crashes) are covered.
  **Zero commitments is byte-identical**: a deterministic six-case harness
  (plain, midday, protected conflict, frozen partial, stability partial,
  crowded) hashes to `e0c5192e…` before and after the change, and the
  prototype oracle still runs 1,000/1,000 with 0 violations.
- **API.** `/api/v1/items` create/list/detail/update/delete plus
  `POST /preview` (baseline vs blocked solve → `displaced`/`dropped`, writes
  nothing) and `POST /confirm` (the write path the assistant will use).
  Ownership is one shared helper (`services/items.get_owned_item`); foreign
  ids are 404, never 403. Private items stay out of the list, remain in the
  owner's detail, and still block solver time. Overlap and sleep-window
  (21:00–05:00) warnings ride on create/preview responses. Every solve route
  (solve, re-plan, forced-include via the shared loader) now plans around
  the day's commitments.
- **Tests.** 11 new (4 solver unit, 7 route integration incl. cross-user
  404s, preview-persists-nothing, recurrence expiry, timezone snapshot with
  DST-free Asia/Tokyo). Full backend suite **137 passed, 1 skipped, 1
  xpassed**. Migration: SQLite stamp→upgrade→downgrade→upgrade clean for the
  new table (the full chain from base remains Postgres-only, a pre-existing
  ARRAY column), and `tools/migration_cycle.sh` on local `postgres:15-alpine`:
  **51/51 checks passed** with the items revision in the chain.
- **Config.** `NVIDIA_API_KEY` documented (empty) in `.env.example`, present
  in the gitignored `backend/.env`, and accepted as an **optional** setting:
  the app boots without it; the Step 2 provider layer must fail clearly only
  when the helper is used. (Adding the key to `backend/.env` before the
  setting existed made pydantic reject the env file at startup — that is
  exactly why the setting landed in this step.)

CI initially caught model/migration drift on the items timestamps
(`Mapped[datetime]` implies NOT NULL; the migration said nullable). Fixed in
the migration and the model; run `44426172912` on `b953370` is fully green
(all five jobs).

## Step 2+3 — provider layer and model benchmark (2026-11-19)

Branch `feat/helper`. Step 4 not started.

- **Provider.** `backend/app/services/llm.py`: key from settings (boots
  without it, fails clearly only when used), OpenAI-compatible NVIDIA
  endpoint, per-model retries (429/5xx/timeout, 1/2/4s backoff), fast→strong
  fallback, status-only errors. The key never appears in code, logs, test
  output or any committed file (scanned). 5 mocked unit tests pass.
- **The named candidates are gone.** All four (nemotron-3-nano-30b-a3b,
  gpt-oss-20b, nemotron-3-super-120b-a12b, llama-3.3-70b-instruct) return
  HTTP 410 — end-of-life 2026-08-26 on NVIDIA's hosted API. Benchmarked the
  same-tier models this key serves instead (10 messy dictations, 3,000-token
  budget — reasoning models emit nothing at 800; repeated passes for the
  shortlist):

  | Model | Pass (runs) | Median | p95 | Max |
  |---|---|---|---|---|
  | nemotron-3.5-bolt-e4b | 4, 4 | 1.18s | 3.58s | 4.62s |
  | nemotron-3-nano-omni-30b-a3b-reasoning | 9, 7, 9 | 4.83s | 16.09s | 18.05s |
  | nemotron-3-ultra-550b-a55b | 8 | 6.04s | — | — |
  | nemotron-3.5-lightning-30b-a3b | 8, 6, 8 | 9.55s | 20.38s | 27.16s |
  | kimi-k3.1-pro | timeout >900s / 10 calls | — | — | — |
  | gemma-3-12b-it / 4b-it | listed but chat 404 | — | — | — |

- **Recommendation (settings defaults updated):** primary
  `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` — the only model to clear
  9/10, though inconsistently (7–9 across runs; failures are
  over-clarification and one Sunday-date slip); fallback
  `nvidia/nemotron-3-ultra-550b-a55b` (8/10, 6.0s, failures are
  over-clarification, which the helper's clarify path absorbs). Bolt is the
  latency champion (p95 3.6s) but stays at ~4/10 strict, ~7/10 with tolerant
  parsing — below the bar. Kimi is unusable at this latency.

## Step 4 — helper endpoint (draft → confirm) (2026-11-19)

Branch `feat/helper`. Text first; no audio stored anywhere (there is no
audio path), and the transcript is stored only on confirm.

- **Draft** (`POST /helper/draft`): transcript → LLM (primary model, 3,000
  tokens — reasoning models starve at the provider default and return
  nothing, which the first live smoke caught) → tolerant JSON parse →
  per-kind validation (items schemas; habits against a habit draft schema)
  → rejected list for unknown kinds or missing required fields (never
  guessed) → clarify passthrough → solver preview of displaced/dropped
  sessions per commitment date. Writes nothing.
- **Confirm** (`POST /helper/confirm`): re-validates everything server-side,
  creates commitments/deadlines as items and habits as behaviours, and
  stores the transcript in `helper_confirmations`, keyed `(user_id,
  draft_id)` so a double confirm returns the original ids instead of
  duplicating rows. Migration `d0e1f2a3b4c5` (new head).
- **Injection posture:** the system prompt treats the transcript as data,
  never instructions; output is constrained to validated draft JSON; the
  confirm path re-validates, so an injected instruction has no write path.
  Tested with a delete-all dictation and an `admin_delete` kind.
- **Verification:** 8 helper tests (mocked LLM) + live smoke against the
  real model on in-memory storage: the example dictation produced the
  deadline (2026-11-16), the 3-day hospital commitment (assumed 120 minutes,
  named in assumptions), and the workout; confirm stored 3 items.
  Full suite **150 passed**; Postgres migration cycle **51/51** with the new
  head; `alembic check` clean; SQLite cycle clean for the new table.

## Step 5 — helper UI, end to end (2026-11-21)

Branch `feat/helper`. The supervised helper now works from the day view.

- **Hardening.** Transcript cap 4,000 chars with a clear 422; per-user draft
  rate limit (10/min default, configurable); draft now retries the primary
  once on unparseable output, then falls back to the strong model (tested
  with a garbage-speaking fake primary: calls were [fast, fast, strong]).
  `GET /helper/status` reports configured-or-not without leaking the key.
- **Habits decision (safe option):** the helper does **not** create
  behaviours. A habit in a draft comes back as `unsupported` — "created in
  the habit form for now" — because the defaults it would need (health
  category, no objective impacts, dormant energy cost) would be silent
  guesses attached to the user's plan. Confirming a habit item is a 422.
- **UI.** Helper panel on the Schedule (day) page and the Dashboard: text
  box, synchronous "Thinking…" state, mapped errors (rate limited,
  not-configured, unavailable, unparseable), clarification question with an
  answer box and resubmit. The confirm card shows each item in plain words
  (kind, local time, recurrence, private badge), editable title/time/date,
  approve-subset checkboxes, highlighted assumptions and warnings, and
  displaced/dropped sessions as plain sentences. Commitments and deadlines
  now render as fixed blocks/chips on the day view (private = lock + text).
  "Voice input is coming soon — typing only for now." No voice claims, no
  fake data.
- **Stale-preview limitation (deliberate):** the displaced/dropped preview
  is computed at draft time and is **not** recomputed at confirm. If the day
  changes between draft and approve, the numbers shown can be stale; the
  items themselves are still created exactly as displayed. Recomputing at
  confirm is future work, not built tonight.
- **Live verification (real browser, real model):** seeded local stack;
  the example dictation drafted 3 items with assumptions, edit of a title
  stuck, confirm added them, the day API returned the 20:00 workout block,
  the fixed row rendered it (a caption line was added after review because
  60-minute blocks truncated the label), reject discarded a second draft,
  "something in the morning" produced a clarification question, and with
  the key removed the panel degrades to a disabled "isn't switched on"
  state. 390px emulation: no horizontal overflow. Suites: backend **157
  passed**, frontend **29 passed**, tsc clean, `alembic check` clean.

## Dashboard upgrade — data truth and week view (2026-11-23)

Branch `feat/dashboard` from `main`. The dashboard now shows the today/week
plan, a compact interactive week calendar (Mon-start, 05:00–24:00), upcoming
commitments/deadlines, and view/edit/delete for an item with an explicit confirm
step and a private toggle. All pre-existing dashboard functions remain reachable.

### Every number names a source

| Surface | Source | Notes |
|---|---|---|
| Plan health rail (7/30 day range) | `GET /api/v1/analytics/summary?days=N` → `DashboardSummary` | Range param now plumbed through; `completionRate`, `released`, `systemDropped` from `compute_range` (`docs/METRIC.md`). |
| Daily trend tiles + sparkline | `GET /api/v1/analytics/series?days=N` (new) | Per-day `completed/baseline/released/dropped/completionRate/plannedMinutes` from `compute_day` + `resolve_day_plan`. Tiles show **range totals with a daily sparkline**, not the latest partial day. |
| Week calendar sessions | `GET /api/v1/schedule?date=…` × 7 | Mon–Sun of the selected week; `releasedAt` and `isCompleted` come from the row. |
| Fixed commitments/deadlines on a day or in Upcoming | `GET /api/v1/items/range?from=…&to=…` (new) | Owner-scoped via `list_owned_items`; private items included for the owner only. Recurrences expanded by `occurrence_on`; 31-day cap. |
| Life map objective shares | Each day's `objectiveScores` from the 7 schedule responses | Averaged across days that reported the objective. The optimization-history endpoint is deliberately **not** used: its runs are dated by creation time and can be empty for a fully planned week. |
| Assistant status / orb state | `GET /api/v1/helper/status` | Unavailable state is distinct; mic is visible but disabled with "Voice is coming soon". |
| Streak / active behaviors / average score | `GET /api/v1/analytics/summary?days=N` | Unchanged fields, still real DB queries. |

A failed request is never rendered as empty data. Each fetch has its own failure
flag; a named banner lists exactly which feeds failed and offers Retry. The
series, upcoming list, and last good per-day schedule are retained on failure; a
day whose schedule failed is marked "Unavailable" rather than "Nothing planned".
Race guards on range and week requests discard stale responses.

Commits are excluded from the completion denominator and reported separately, as
`docs/METRIC.md` requires. Four backend truth fixes back this up:

- `GET /schedule` exposes `releasedAt` (`ScheduledBehaviorResponse`), and a
  released session renders as "Released" — it is neither pending nor completed.
- Completion is keyed on `planned_session_id` in `GET /schedule`, in
  `mark_complete`, in `mark_incomplete`, and in the summary's check. A behaviour
  scheduled twice in a day is now completed one session at a time.
- The release route's completion check is scoped to the run as well as the
  session id.
- New regression `test_schedule_completion_is_per_session_and_exposes_release`
  in `backend/tests_integration/test_session_identity.py` pins all four.

### Frontend

New components: `WeekCalendar` (keyboard ArrowUp/Down within a day, Enter/Space
to open, distinct released/completed styling and labels, unavailable-day state),
`DayDetailPanel` (session complete/incomplete/release, item view with confirm +
private toggle, recurring-delete wording, agenda rows open in the same panel),
`InsightTiles` (range totals, sparkline, failed state), `LifeMap` (SVG orbit over
the week's averaged `objectiveScores`, label clipping fixed), `PlanHealthRail`,
and `HelperOrb` (six distinct states, Retry placement, disabled mic). Dead
`StatsCards.tsx` removed. Voice remains unbuilt; no drag-and-drop rescheduling.
SVG + CSS only, no new libraries, `motion-safe:` for all animation so
`prefers-reduced-motion` is respected. Landing tokens reused unchanged.

New/updated frontend regression tests cover: orb unavailable state, released and
completed session states, ArrowUp/Down, unavailable day, local status update,
released-action gating, delete failure, recurring-delete wording, agenda-row
navigation, InsightTiles range totals and failed state, LifeMap, dashboard
failure banner, and life-map-from-week-schedules. New backend integration test
`test_dashboard_data.py` covers the series endpoint and the range endpoint.

### Real output — gates

```
backend:  uv run pytest -q -p no:cacheprovider
          163 passed, 1 skipped, 1 xpassed, 1 warning in 99.51s
backend:  uv run alembic check  ->  No new upgrade operations detected.
frontend: npx tsc --noEmit      ->  clean
frontend: npm test -- --run     ->  52 passed, 7 files
frontend: npm run build         ->  ✓ built in 48.74s
frontend: npm run lint -- --max-warnings=20
                              ->  0 errors, 11 warnings (all pre-existing)
```

No schema changes were made in this phase; `alembic check` was re-run with
Postgres up and reports no drift. `conversation-*.txt` exports are now ignored
(`.gitignore`), never committed. The temporary metric profiler was removed.

### Real output — live browser verification

Real Edge CDP at three viewports against the local stack (Postgres container,
backend :8000, Vite :8080), seeded user `test@example.com`. A solve for
2026-11-23 produced 13 sessions and 8 objectives; the range endpoint returned 4
fixed entries for the week.

| Viewport | innerWidth | body/doc scrollWidth | Week days | Overflow | Exceptions |
|---|---|---|---|---|---|
| 1440×950 | 1440 | 1440 / 1440 | 7 | none | none |
| 1366×768 | 1366 | 1366 / 1366 | 7 | none | none |
| 390×844 (mobile override) | 390 | 390 / 390 | 7 | none | none |

Interactions exercised in the browser: opened a pending session, clicked **Mark
complete** → badge became `COMPLETED` and notice `Marked complete.`, then
reverted with **Mark incomplete**; opened a fixed item, opened **Edit** → form
rendered; switched the range chip 7→30 days; only console output was the React
Router future-flag warning. Screenshots and the machine-readable report are in
the local temp workspace, not committed.

### Endpoint latency (clean measurement)

The first pass measured 18–20 s for 7d/30d calls. That was **not** the endpoint:
three stale uvicorn processes were competing for the Postgres pool. After
stopping them and running one clean backend, direct API timings (Node fetch,
warm DB) were:

| Endpoint | 7 days | 30 days |
|---|---|---|
| `/analytics/summary` | 310–835 ms | 456–481 ms |
| `/analytics/series` | 339–406 ms | 670–746 ms |

A SQL-level profile of `compute_range` confirmed 7 and 30 queries respectively
(~125–280 ms including first-query warmup), so the existing per-day queries are
fine and **metric batching was not introduced**. Documentation: the earlier
slow numbers were environmental, not a product regression.

### Known gaps (unchanged, deliberate)

- Preview is not recomputed at helper confirm; deadline prep blocks are not
  turned into sessions; helper-created habits are refused (422); there is no
  audit row for rejected/failed drafts.
- Voice input and the full items list page are not built. The mic is visible but
  disabled with "Voice is coming soon".
- Muse Wonder / Spark / Ember were unavailable this session; work was done
  directly with no silent substitution.

---

## Needs a decision

1. **Settled in Phase 1.5:** `scratch/` is ignored and the scripts live in
   `tools/`; the two grading documents are archived in `docs/archive/` with a
   note. Nothing to decide.
2. **Next, if you want the metric to be real:** a release endpoint and a retire
   path are needed before release/retire can be counted. Deferred deliberately -
   they are product surface, not schema.

---

## Dashboard polish - objective colour and a readable week (2026-11-24)

Branch `feat/dashboard-polish`, created from `main` after PR #6 merged
(`4edac8a7747b90061f227c8aac7c405927b3bdbf`). No backend, schema or metric
changes; every value on the screen still comes from the existing dashboard
feeds.

### The objective is the real highest impact

`objective_impacts` stores one row per `objective_type` with an `impact_score`
from -1 to 1. The session colour now uses `highestImpactObjective()`: the row
with the highest finite score, ties broken alphabetically, and no usable score
means `Unassigned`; it is **not** the first row returned. Tests pin the
highest-score case, the tie, empty rows and `NaN`.

The palette is fixed and shared by the calendar and life map: eight
Okabe-Ito-inspired hues, one shape and a short code per objective. Commitments
stay neutral, dashed and hatched with a lock; deadlines stay flags; released
sessions stay faded/hatched. Colour is never the only cue. The same values are
declared in `frontend/src/index.css`; a test reads that file and fails if the
CSS and `objectivePalette.ts` drift.

| objective | light ink / tint | dark ink / tint |
|---|---:|---:|
| Health | 6.40:1 | 10.22:1 |
| Productivity | 5.76:1 | 9.40:1 |
| Learning | 5.93:1 | 9.20:1 |
| Wellness | 6.30:1 | 9.90:1 |
| Social | 5.71:1 | 8.75:1 |
| Financial | 6.32:1 | 11.43:1 |
| Creativity | 6.14:1 | 10.73:1 |
| Mindfulness | 12.62:1 | 11.74:1 |

All eight clear WCAG AA for normal text (4.5:1); the lowest pair is Social
light at **5.71:1**. The tests also check each ink against the white card and
the dark card. The light Creativity swatch is low-contrast as a fill, so its
orb also carries the darker ink stroke and a cross shape.

### Calendar

- Desktop uses **72 px per hour**, so a 15-minute block is 18 px; the
  05:00-24:00 grid is 1,368 px tall. The page scrolls, not an inner box, and the
  dashboard content uses the full width next to a sticky sidebar.
- Overlapping sessions and commitments share a day cluster and sit side by
  side; overlap width is computed from the cluster, not hard-coded.
- Titles can use two lines; the objective code and time moved to a quieter
  meta line. Axis labels render once on the first day column instead of seven
  times. The legend lists only objectives present in the visible week and
  explains commitments, released sessions and deadlines.
- At 390 px the seven-day strip remains and the seven-column grid is replaced
  by a single-day agenda. Sessions and commitments are **merged and sorted by
  start time**, with the deadline flag first; the day agenda also opens from
  the strip. `data-objective` is present on desktop and mobile session buttons.
- After the helper confirms, the status now says what was added and offers
  **Plan my week to fit it in**. Until Part B exists, that link goes to the
  existing Optimization page.

### Real output - gates

```
frontend: npx tsc --noEmit      -> clean
frontend: npm test -- --run     -> 61 passed, 8 files
frontend: npm run build         -> built in 41.04s
frontend: npm run lint          -> 0 errors, 12 warnings (existing patterns)
```

The build warning is the existing >500 kB chunk notice. No new dependency was
added; the calendar and life map are still SVG + CSS.

### Real browser evidence

The host clock is Tuesday 24 Nov 2026. Because the request asked for the busiest
day as "Monday today", the page clock was pinned to Monday 23 Nov 2026 10:30
through CDP. The seeded week is 2026-11-23 to 2026-11-29: **13 sessions, 4
commitments, 1 deadline, busiest Monday (480 min)**. Screenshots are full-page;
the visible window was clamped by the 1366x768 screen, so a headless Brave
session over CDP provided the exact viewports.

| viewport | innerWidth | document scrollWidth | day buttons | session buttons | grid height | overflow |
|---|---:|---:|---:|---:|---:|---|
| 1366x768 | 1366 | 1351 | 7 | 13 | 1368 px | none |
| 1440x950 | 1440 | 1425 | 7 | 13 | 1368 px | none |
| 390x844 | 390 | 390 | 7 | 13 | mobile agenda | none |

At 390 px the seven-column grid is absent and the agenda heading reads
`Mon, Nov 23`; the merged order around the morning commitment was
`Team Sync 07:30-07:45`, `Take father to hospital 08:00-10:00`,
`Gym Session 10:00-11:30`. `main` computed `overflow-y: visible` at every
viewport, confirming the page, not an inner pane, scrolls. Reduced motion was
emulated at 1366x768: `matchMedia('(prefers-reduced-motion: reduce)')` matched,
the pulse animation name was `none` and its duration `1e-05s`. The console held
only Vite/React development messages and the React Router future-flag warning;
no application exceptions.

Screenshots:

- `docs/images/phase5-dashboard-1366x768.png`
- `docs/images/phase5-dashboard-1440x950.png`
- `docs/images/phase5-dashboard-390x844.png`
- `docs/images/phase5-dashboard-reduced-motion.png`

### Not built

"Plan my week" is **not** built in this branch. The helper confirmation uses
the existing Optimization link as the interim action, as requested. The
read-only Part B research is separate and stops for approval before any
seven-day solve or apply/preview UI is added.

---

## Phase 6 amendment — carry-over, solver busy, browser evidence

**Changed**

- `GET /schedule` now resolves completion from `planned_session_id`, not
  `optimization_run_id`. A session completed in run A stays completed after a
  re-plan creates run B, keeps its slot, and is counted once even if a duplicate
  completion log exists.
- The week-plan dialog formats the range as `Planning Tue 24 to Sun 29` instead
  of `Planning 24 Tue to 29 Sun`.
- Regression coverage added in
  `backend/tests_integration/test_week_planning.py`:
  - completed session stays completed after re-plan and is counted once
  - completed session is absent from `moved` and `dropped`
  - carried-session plan-health numbers do not change; the genuinely dropped
    session moves from `missed` to `system_dropped` exactly once
  - a saturated solver pool makes every plannable day return a per-day
    `solver_busy` result sourced from the 503 `SolverBusyError`

**Real test output**

```
backend focused week suite: 13 passed
backend full suite:         176 passed, 1 skipped, 1 xpassed
frontend suite:             70 passed
```

**Plan Health: `0 released, 2 dropped`**

This is a real re-plan of **Tue 24 Nov 2026**, not stale seed data:

- baseline run `da0edcbb81aa4ef8bba3f1f1e2f23ec1` (`plan_revision=1`) had
  5 sessions and no releases
- re-plan run `1885e4f9b817420a819cbca526b25e98` (`plan_revision=2`) retired two
  baseline sessions that were not carried forward:
  `fcef546a337d4a69a54025f00d0934ee` (Deep Work, period 40) and
  `dc9dc18d503f424e9aaabc61b3a95315` (Healthy Cooking, period 52)
- no session had `released_at`, so `released=0`; the two retired sessions are
  what Plan Health counts as `system_dropped=2`

On the host date **Wed 25 Nov** those numbers belong to the previous day's
baseline, so they are stale for that date.

**Pinned browser pass**

The host clock stayed on **Wed 25 Nov 2026**. The backend process was pinned to
`2026-11-24T12:00:00Z` with `clock.fixed_now`, and Playwright installed the same
pinned time in the page. The browser therefore saw **Tue 24 Nov 2026** while the
system clock was not changed.

Actual run:

- login OK; today's plan source was `committed` before the re-plan
- one protected session was completed through the real API
- future drafts seeded through the real preview/apply API for **5 days**
- main preview: **5 of 7 days can be planned**, **2 unavailable**
  - `Mon 23`: `past_day`
  - `Tue 24`: real `solver_error`, `Team Sync: period 24/25 outside its time windows`
- apply: **5 days applied**; skips were `Mon 23 past_day` and
  `Tue 24 not_selected`
- the protected completed session stayed at `06:00-06:30`, stayed
  `isCompleted: true`, and remained absent from both `moved` and `dropped`
- second run: **5** `No changes to this day.` entries
- stale mutation: apply returned **409** with `week_plan_changed`; the UI showed
  **This preview is out of date.** and the refresh button
- viewports **1366x768**, **1440x950**, **390x844** had no horizontal overflow
- the only console error was the expected 409; no page errors or failed requests
- mocked solver-busy evidence: one future day (`Wed 25`) was given a
  Playwright-injected per-day `solver_busy` result modelling the backend's 503.
  The screenshot is labelled **MOCKED**; this is not claimed as a live
  saturation run. The real 503 path is covered by the backend pool test.

Screenshots:

- `docs/images/phase6-week-plan-initial-1366x768.png`
- `docs/images/phase6-week-plan-loading-1366x768.png`
- `docs/images/phase6-week-plan-next-week-1366x768.png`
- `docs/images/phase6-week-plan-preview-1366x768.png`
- `docs/images/phase6-week-plan-applied-1366x768.png`
- `docs/images/phase6-week-plan-filled-1366x768.png`
- `docs/images/phase6-week-plan-no-changes-1366x768.png`
- `docs/images/phase6-week-plan-stale-1366x768.png`
- `docs/images/phase6-week-plan-solver-busy-MOCKED-1366x768.png`
- `docs/images/phase6-week-plan-1440x950.png`
- `docs/images/phase6-week-plan-390x844.png`
- `docs/images/phase6-week-plan-zoom-draft-plan.png` (3x device scale)
- `docs/images/phase6-week-plan-zoom-committed-plan.png` (3x device scale)

**Notes**

- The seeded week can produce a real `solver_error` on today when the protected
  completion forces `Team Sync` outside its time windows; that is why the live
  apply count is 5 rather than 6. It does not affect the protected-session
  carry-over result.
- The zoomed header captures use a separate 3x device-scale context because CSS
  zoom produced blank element screenshots.
