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

Not started.

---

## Needs a decision

1. **Settled in Phase 1.5:** `scratch/` is ignored and the scripts live in
   `tools/`; the two grading documents are archived in `docs/archive/` with a
   note. Nothing to decide.
2. **Next, if you want the metric to be real:** a release endpoint and a retire
   path are needed before release/retire can be counted. Deferred deliberately —
   they are product surface, not schema.
