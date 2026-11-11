# Part B — design findings (design only, no code changed)

Status: proposal. No application code, schema, or solver formulation was modified
for this document. Benchmark/verification scripts live in `scratch/` and are not
committed.

Scope note on numbering: B1–B7 are recorded here as *formulation → tiering →
energy → plan snapshot & metric → result contract → cost-to-fit → partial re-solve*.
If your list differs, only the numbering changes; the substance below is keyed to
the problem each item addresses.

Evidence references are to current `HEAD`.

---

## B0. Shared context (why these seven hang together)

Today's engine is a **single-shot daily planner**:

- one MILP per request, weighted-sum maximisation over a 96-period binary matrix
  (`backend/app/optimization/solvers/linear.py`);
- one `OptimizationRun` per solve, one `ScheduledBehavior` row per emitted session;
- completion is recorded per *(run, behavior)*, not per session
  (`backend/app/api/v1/schedule.py::mark_complete`);
- objective weights are read from `Objective.weight` and frozen into the run's
  `results` (`schedule.py` `objective_contributions`).

The adaptive-coach goal needs three things the current model cannot express:
an explicit *commitment* (what I promised), an explicit *refusal* (what did not
fit), and *stability* (re-planning should not silently rewrite history). B4 and
B5 create the commitment/refusal vocabulary; B7 makes re-planning stable; B1–B3
and B6 are the levers that make the plan worth committing to.

---

## B1. Formulation: complete feasible candidate set vs. single best

**Problem.** `solve()` maximises a weighted sum and returns one schedule. The user
sees a plan with no sense of the alternatives that were nearly as good, so a plan
that "feels wrong" can only be changed by editing behaviours and re-solving blind.
The objective also mixes impacts and duration (`impact × minutes × weight`), so
"more of the highest-impact behaviour" beats "a balanced day" by construction.

**Design.**
1. Default mode returns a **small, explicitly distinct candidate set** (N = 3):
   solve once for the best plan, then re-solve with a *no-good cut* excluding
   that assignment, up to N times (or N−1 extra solves with a time cap).
2. Each candidate carries the same `OptimizationSolution` shape plus a
   `difference_from: candidate_id` summary (which sessions moved).
3. Keep the current single-solution path as `mode="best"` for the existing UI and
   for partial re-solve.

**Recommendation.** Ship the candidate set as the default for *initial* planning
only; re-planning keeps `mode="best"` so adaptation stays deterministic.

**Strongest argument against.** N× the solve cost on a synchronous endpoint that
already runs on 2 workers with no queue (H7), and a candidate set pushes the
decision back onto the user — the opposite of a coach that says "here is your day".

**Reversal cost.** Low: mode flag plus a loop; nothing in the schema changes if
candidates stay inside `results`.

---

## B2. Tiering: protected-first, no silent drops

**Problem.** There is no notion of a non-negotiable item. When the day is
oversubscribed the solver simply leaves lower-impact behaviours unscheduled and
still reports `status="completed"`. The user cannot tell "did not fit" from
"was not wanted", which makes the plan untrustworthy (M-series finding on silent
drops).

**Design.**
1. Behaviours gain `protection: NONE | PREFERRED | PROTECTED` (default `NONE`).
2. Solve in **tiers**: satisfy hard constraints and all `PROTECTED` inclusions
   first (lexicographic), then maximise the weighted sum of the rest.
3. If the protected set itself cannot be satisfied, return
   `status="protected_conflict"` with the minimal conflicting subset (the IIS-like
   set can be approximated by relaxing one protected item at a time).
4. `PREFERRED` items are "best effort, rank above NONE" — implemented as a large
   but finite weight bonus, not a hard constraint, so a single preference cannot
   make the day infeasible.

**Recommendation.** Tiers as above, with `PROTECTED` capped at a small number per
day (e.g. 5) enforced at the API, because each one removes slack.

**Strongest argument against.** Lexicographic tiering can trade an arbitrarily
large amount of objective value for one protected item, and users will mark
everything protected if the UI lets them; combined with B1 the search space is
multiplied.

**Reversal cost.** Medium: schema column + migration, solver restructure, new
result status (shared with B5), UI affordance.

---

## B3. Energy: stop claiming it, keep the column

**Problem.** `energy_cost` is collected (1–10) and totalled for display
(`schedule.py` `total_energy_spent` sums `behavior.energy_cost` *per session*,
which is dimensionally meaningless), but the solver never constrains it and there
is no energy budget model. `analytics.py` returns a hardcoded
`energy_spent=0, energy_budget=100` series. The product claims energy-awareness it
does not have.

**Design.**
1. Remove energy from user-facing claims and from the dashboard until a real model
   exists: drop the mock series, label the schedule's energy figure as
   "estimated effort" or hide it.
2. Keep `energy_cost` in the schema and in the API (dormant), so a future
   `energy_budget` constraint can use it without a migration of user data.
3. If/when modelled: add a `time_budget`-style constraint keyed on
   `Σ x[b,t] · energy_cost[b]` with an explicit daily budget, and define whether
   energy is per-session or per-minute before exposing it.

**Recommendation.** Do step 1 now; do steps 2–3 only with a user-visible budget
control, otherwise the field is noise.

**Strongest argument against.** Energy is the one thing that distinguishes a
*behavioural* planner from a calendar; removing it weakens the product story at
exactly the moment we are trying to justify the coach framing.

**Reversal cost.** Trivial for step 1; a real energy model is a formulation change
with its own calibration problem (self-reported 1–10 is not comparable across users).

---

## B4. Committed plan snapshot and the completion metric

**Problem (most important item).** Completion is stored as
`CompletionLog(user_id, behavior_id, optimization_run_id)` and looked up by
*(run, behavior)* in `mark_complete`, so:
- a behaviour scheduled twice in a day can only be completed once (C4);
- `ScheduledBehavior` has no stable identity across re-plans, so "the 10:00 run"
  cannot be completed after a re-solve moved it;
- the dashboard denominator is `count(ScheduledBehavior)` for runs created in the
  last 7 days (`analytics.py`), so each re-plan inflates the denominator and a
  re-plan *resets* progress instead of carrying it forward.

**Design.**
1. **`PlannedSession`** — stable id for a scheduled session (behaviour, date, start
   period, duration). `ScheduledBehavior` rows reference it; a re-plan either keeps
   the id (session unchanged), moves it (id kept, period updated, `revision` bumped),
   or retires it (id kept, `retired_revision` set).
2. **`Plan` revision chain** — a committed `Plan` is immutable. Re-planning creates
   `Plan(revision+1, parent=revision)` that references the same `PlannedSession`
   ids. Nothing is deleted.
3. **Completion** attaches to `PlannedSession` (+ `plan_revision` for provenance).
4. **Metric**: `completion_rate = completed_session_ids / committed_session_ids`
   within one committed Plan (latest revision at the time of measurement), with
   retired sessions counted in the denominator and carry-forward applied to moved
   sessions. A re-plan never resets the denominator.
5. **Minimum viable slice now**: add a stable `planned_session_id` to
   `ScheduledBehavior` (uuid, generated at first materialisation) and record
   completion against it, keeping the existing per-behaviour uniqueness rule until
   the Plan table lands.

**Recommendation.** Do the minimum viable slice (stable session id + completion per
session) before any of B1/B2, because it is the prerequisite for measuring whether
those changes help. Then the revision chain, then the metric switch.

**Strongest argument against.** A frozen denominator punishes legitimate change: if
the user's day collapses and they re-plan to three easy sessions, a metric anchored
to the original twelve makes the product look like it is failing them, and users
will learn to avoid re-planning — the exact behaviour the coach is supposed to
encourage.

**Reversal cost.** High: data migration, every completion/progress query, the
dashboard, and the "which plan am I looking at" question in the UI.

---

## B5. Result contract: distinguish refusal from success

**Problem.** `OptimizationSolution.status` accepts
`optimal | feasible | infeasible | unbounded`, but the API persists non-optimal as
`"feasible"` and maps it onto `OptimizationStatus`, which has no `feasible` member
(C3). `PULP_CBC_CMD(timeLimit=...)` returns `LpStatus=Not Solved` on timeout with a
possible incumbent; the solver treats that as success with
`total_objective_value = 0`, and the `except TimeoutError` branch is unreachable
(H3). Infeasibility surfaces as HTTP 500 with internal text (H10).

**Design.**
1. Explicit enum: `OPTIMAL | FEASIBLE | PARTIAL (timeout with incumbent) |
   INFEASIBLE | PROTECTED_CONFLICT | UNBOUNDED | SOLVER_ERROR`.
2. Timeout detection from PuLP, not exceptions: `status == 0` (Not Solved) and
   `sol_status == 2` (Solution Found) means *partial with incumbent*; record
   `objective_bound` when available.
3. Map statuses to HTTP: 200 for OPTIMAL/FEASIBLE/PARTIAL (with `status` +
   `explanation`), 422 for INFEASIBLE/PROTECTED_CONFLICT (structured, with the
   conflicting items), 504 for timeout with no incumbent, 500 only for genuine
   solver errors.
4. Every refusal carries a machine-readable reason list plus a human sentence —
   mandatory, not optional (product decision from Phase 2).

**Recommendation.** Do this with B2, since `PROTECTED_CONFLICT` is meaningless
without it; the timeout fix should ship independently and immediately.

**Strongest argument against.** Each status is a UI state that has to be designed
and tested; six statuses invite five ways to show "something went wrong" and the
frontend currently has zero `useQuery`/`useMutation` plumbing to drive them (H11).

**Reversal cost.** Low–medium: enum + mappings + UI copy; no data migration if
existing rows keep `"feasible"` as a legacy value.

---

## B6. On-demand "cost to fit X"

**Problem.** The optimizer can only answer "what is my best day?" It cannot answer
the question users actually ask: *"I want to add a 45-minute gym session — what
gives?"* Today that requires editing behaviours, re-solving, and diffing the
schedule by eye.

**Design.**
1. `POST /optimization/cost-to-fit` with `{behavior_id | ad-hoc behavior,
   duration, day}`; solve the **current plan** with the item force-included as a
   hard constraint, everything else unchanged (same tier rules as B2).
2. Response: `feasible: bool`, `displaced[]` (sessions removed or shortened),
   `objective_delta`, `explanation`.
3. When infeasible, return the minimal relaxation set ("if you shorten Deep Work
   to 45 min it fits") by relaxing the cheapest constraints first.
4. Cache by (plan revision, request hash); cap at one solve, short timeout.

**Recommendation.** Build it — it is the single most valuable "decision support"
surface and it reuses the existing solve, not a new formulation.

**Strongest argument against.** It turns a synchronous, 30 s-timeout endpoint into
an interactive one, and a "no, it does not fit" answer on a lark is a worse
experience than not asking — the feature only lands if the relaxation suggestions
are good, which is the hardest part.

**Reversal cost.** Low: additive endpoint; risk is latency and perceived quality,
not schema.

---

## B7. Partial-day re-solve redesign

**Problem.** `partial_reoptimize` (`backend/app/api/v1/schedule.py`) has four
defects that compound:

1. **Duplication.** It appends one `BehaviorScheduleInput` per *scheduled row*, so
   a behaviour with two sessions enters the problem twice. The solver then treats
   them as independent behaviours; duration bounds and objective credit double.
2. **Wrong clock.** `now = datetime.now(timezone.utc)` is compared with
   `target_date = date.today()` (server-local) and with plan periods that are
   plan-local; in any non-UTC timezone the freeze line is off by the offset.
3. **Global freeze.** `earliest_free = max(frozen) + 1` freezes *every* behaviour
   up to the latest frozen period, so one early-morning session blocks re-planning
   the whole morning for everything else.
4. **Inactive behaviours are still carried.** The query has no `is_active` filter,
   so a deactivated behaviour with a session later today stays in the problem and
   can be rescheduled.
   Also: it writes `status="feasible"` on non-optimal results (same C3 defect) and
   creates a new independent `OptimizationRun` rather than a revision of the plan.

**Design.**
1. **Plan-local clock.** Store the plan's timezone on the `Plan`/run; convert `now`
   into plan-local time once and derive `current_period` from that. `date.today()`
   is replaced by `plan.local_date`.
2. **Session-level freeze.** Freeze by *session*, not by global period: for each
   elapsed session, pin its periods to their realised value (1 if completed, 0 if
   missed) and pin its identity so it cannot be moved. Future sessions of the same
   behaviour remain free.
3. **Distinct behaviours.** Build one `BehaviorScheduleInput` per behaviour id
   (dedupe), with frozen minutes aggregated per behaviour; carry completed minutes
   forward as *already satisfied* duration rather than re-imposing `min_duration`.
4. **Deactivated behaviours.** Exclude future sessions of `is_active=False`
   behaviours from the re-plan (they are not scheduled again), while their
   **elapsed** sessions stay frozen exactly like any other elapsed session. This is
   a hard requirement: a deactivation takes effect from the next unfrozen period,
   and it must never rewrite what already happened. The new plan revision records
   the exclusion so the regression is auditable, and the returned schedule lists
   retired sessions explicitly.
5. **Stability term.** Add a soft penalty `λ · disruption` (moved sessions, minutes
   moved) to the objective so the re-solve prefers the smallest change that meets
   the requirements; `λ` is a constant with a documented default, not a user knob.
6. **Revision, not fork.** The new solve creates `Plan(revision+1, parent=...)`
   sharing `PlannedSession` ids (see B4), so completions and the metric survive.
7. **Contract.** Reuse B5 statuses; persist the actual solver status instead of
   `"feasible"`.

**Recommendation.** Sequence: (a) plan-local clock + dedupe + status fix — pure
correctness, no new concepts; (b) elapsed-session freeze + deactivated exclusion;
(c) stability term; (d) plan revisions (depends on B4's session ids).

**Strongest argument against.** Elapsed-session freezing plus deactivation
exclusion can make the remaining day infeasible (a missed protected session cannot
be rescheduled, and the rest of the day may not have room), so the honest answer
becomes "your day no longer fits" — correct, but it is exactly the moment users
churn. The stability penalty also makes results harder to explain ("why did it
leave a gap?") and adds a tuning constant we cannot validate without real usage.

**Reversal cost.** Medium–high: touches the solver's partial path, the run/plan
model, and the schedule API; the deactivation rule is easy to state and hard to
undo once users rely on it.

---

## Recommendation summary

| # | Item | Recommendation | Confidence |
|---|------|----------------|-----------|
| B1 | Candidate set | initial planning only, N=3 | medium |
| B2 | Protected tiers | yes, with a cap and `PROTECTED_CONFLICT` | high |
| B3 | Energy | stop claiming it; keep the column dormant | high |
| B4 | Plan snapshot + metric | minimum viable slice first (stable session id) | high |
| B5 | Result contract | yes; timeout fix immediately | high |
| B6 | Cost to fit X | yes, after B2/B5 | medium-high |
| B7 | Partial re-solve | correctness first (clock, dedupe, inactive), then stability | high |

Ordering that minimises rework: B5 (timeout/status truth) → B4 slice (session ids +
completion per session) → B2 (tiers) → B7 correctness → B3 (claims cleanup) →
B6 → B1 → B7 stability + plan revisions.

**Gates before any predictive/LLM layer:** a session-level completion metric, an
explicit refusal contract, and a stable plan revision chain. Without those, any
"coach" advice is unfalsifiable.
