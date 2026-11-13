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

## Phase 2 — Sessions you can count

Not started. Waiting on the Phase 1 review, as instructed.

## Phase 3 — The planner itself

Not started.

## Phase 4 — Re-planning that works

Not started.

---

## Needs a decision

1. **`scratch/` in version control** — ignore it, keep it untracked, or commit the
   benchmark scripts? Nothing is blocked, but the tree is not clean until this is
   settled.
2. **The two grading documents** — `GRADING_CHECKLIST.md` and
   `docs/README_UPGRADE_SUMMARY.md` still assert the old AI framing and the dead
   deployment URL. Delete, rewrite, or leave as historical artefacts?
