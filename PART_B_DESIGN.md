# Part B — design findings

**Design only. No application code, schema, or solver formulation was changed for
this document.** Measurements were produced by throwaway scripts in `scratch/`
(not committed); reproduction commands are in §10.

## 0. Mapping to the requested items

| Item | Requested | Where |
|------|-----------|-------|
| a | Measured CBC benchmark (10/20/40 behaviours; fixed/variable durations; narrow/wide windows) | §1 — **measured** |
| b | Forced real CBC timeout in PuLP 2.8.0, with and without an incumbent | §2 — **measured** (one half not observable; see §2.3) |
| c | Protected-conflict behaviour + suggested minimal relaxation, never auto-drop | §3 |
| d | Denominator rule: system-dropped stay, user-released leave and are reported | §4 |
| e | Two or three definitions of the committed baseline moment | §5 |
| f | Staged schema, now vs deferred, and what forces the fuller model | §6 |
| g | Brute-force oracle test plan for tiny instances | §7 |
| h | Re-solve redesign incl. excluding future sessions of deactivated behaviours | §8 |

Cross-cutting decisions required by the brief: PREFERRED tier (§9.1 — **dropped**),
PARTIAL vs FEASIBLE (§9.2), three-distinct-plans (§9.3 — **deferred**).

---

## 1. Item a — measured CBC benchmark of the candidate-placement formulation

The formulation measured is the one in
`backend/app/optimization/solvers/linear.py`: 96 binary periods per behaviour
(`x[b,t]`), exclusivity per period, preference windows, and per-behaviour duration
bounds. Objective: weighted sum of impact × scheduled minutes. CBC via
`PULP_CBC_CMD(timeLimit=60, msg=0)`. Windows: **narrow** = `morning` (300 min of
capacity), **wide** = `flexible` (1140 min). Durations: **fixed** = exactly 15 min,
**variable** = min ∈ {15,30,45}, max = min + {15,30,45}.

| n | durations | windows | capacity | status | objective | sessions | seconds |
|---|---|---|---|---|---|---|---|
| 10 | fixed | narrow | 300 | optimal | 5.014 | 10 | 0.331 |
| 10 | fixed | wide | 1140 | optimal | 4.944 | 10 | 0.318 |
| 10 | variable | narrow | 300 | optimal | 10.66 | 19 | 0.356 |
| 10 | variable | wide | 1140 | optimal | 22.232 | 37 | 0.331 |
| 20 | fixed | narrow | 300 | optimal | 10.396 | 20 | 0.593 |
| 20 | fixed | wide | 1140 | optimal | 11.936 | 20 | 0.512 |
| 20 | variable | narrow | 300 | **InfeasibleProblemError** | — | — | 0.705 |
| 20 | variable | wide | 1140 | optimal | 41.65 | 72 | 0.810 |
| 40 | fixed | narrow | 300 | **InfeasibleProblemError** | — | — | 1.123 |
| 40 | fixed | wide | 1140 | optimal | 21.21 | 40 | 1.122 |
| 40 | variable | narrow | 300 | **InfeasibleProblemError** | — | — | 0.902 |
| 40 | variable | wide | 1140 | **InfeasibleProblemError** | — | — | 0.956 |

**Interpretation.**

1. **Solve time is not the bottleneck at these sizes.** The largest feasible
   instance (40 behaviours, wide) is optimal in **1.12 s**; 10–20 behaviours are
   0.3–0.8 s. CBC is fast here because preference windows are permissive and the
   LP relaxation is close to integral.
2. **The binding constraint is capacity, not combinatorics.** The infeasible rows
   are arithmetic: 40 variable-duration behaviours need ≈1200 min of minimum
   duration against 1140 min available ("wide"), and 300 min of window against
   600+ min of minimum duration ("narrow"). Infeasibility is detected in
   ~0.7–1.1 s, which is acceptable for a synchronous call but means "your day does
   not fit" is a routine outcome, not a rare one — see §3.
3. **Sessions are not bounded by anything the user set.** The 20/wide/variable row
   emits **72 sessions** for 20 behaviours (CBC spreads each behaviour over many
   short blocks because the objective is linear in minutes and nothing rewards
   contiguity). The post-processing merges consecutive blocks, so 37–72 sessions
   for 20 behaviours is the measured consequence of the missing contiguity
   constraint (H6).
4. **A candidate-set mode would cost ~2–3× these numbers** (one extra solve per
   candidate), i.e. ~1–3.5 s at 40 behaviours — affordable, but see §9.3 for why
   that is not the reason to defer it.

Caveat: these are one machine (Windows, local CPU), one CBC build, 12 instances
with a fixed seed. They establish order of magnitude, not a performance guarantee.

---

## 2. Item b — forced real CBC timeouts in PuLP 2.8.0

All runs used `pulp.__version__ == "2.8.0"` and `PULP_CBC_CMD(timeLimit=…, msg=0)`.
`pulp_status` is `LpStatus`, `sol_status` is `LpSolution`.

### 2.1 Without an incumbent (time limit hit before any proved solution)

| instance | limit | pulp_status | sol_status | objective | values integral? |
|---|---|---|---|---|---|
| 3-dim knapsack, 2000 items | 0.1 s | 0 `Not Solved` | 0 `No Solution Found` | 128177.13 | no (see 2.3) |
| 3-dim knapsack, 4000 items | 0.1 s | 0 `Not Solved` | 0 `No Solution Found` | 256449.99 | no |
| 3-dim knapsack, 8000 items | 0.1 s | 0 `Not Solved` | 0 `No Solution Found` | 512889.30 | no |
| set cover 1200×1800, d=5 | 0.02 / 0.05 / 0.1 / 0.3 s | 0 `Not Solved` | 0 `No Solution Found` | 489.2464 (identical at all four limits) | **false** |

Reference optima obtained with a long limit on the same instances: knapsack
128138 / 256372 / 512806; set cover **493** (2.0 s, status 1). The timed-out
objectives are therefore **relaxation bounds, not achievable plans**:
- maximisation: reported 128177 > true optimum 128138;
- minimisation: reported 489.25 < true optimum 493.

`LpProblem.objective.value()` is populated on a `Not Solved` solve, and `varValue`
is populated for every variable, so code that checks `value is not None` will
believe it has a plan. On the set cover instance the values were **fractional**
(`integer_valued: false`) yet still "covered" every element when compared with
`>= 1` on summed floats — a plausible-looking but illegal answer.

### 2.2 With an incumbent

I could **not** produce `pulp_status = 0 (Not Solved)` together with
`sol_status = 2 (Solution Found)` in any of the real runs. What CBC/PuLP actually
reported whenever a solution existed:

| instance | limit | pulp_status | sol_status | objective |
|---|---|---|---|---|
| 3-dim knapsack 2000 | 0.5 s | 1 `Optimal` | 2 `Solution Found` | 128138 |
| 3-dim knapsack 4000 | 0.5 s | 1 `Optimal` | 2 `Solution Found` | 256372 |
| 3-dim knapsack 8000 | 0.5 s | 1 `Optimal` | 2 `Solution Found` | 512806 |
| set cover 600 sets | 0.5 s | 1 `Optimal` | 1 `Optimal Solution Found` | 291 |
| set cover 1200 sets | 0.5 s | 1 `Optimal` | 2 `Solution Found` | 501 |
| set cover 1200 sets | 2.0 s | 1 `Optimal` | 2 `Solution Found` | 493 |
| knapsack 2000, `maxSolutions 1` | 10 s | 1 `Optimal` | 2 `Solution Found` | 128151 |
| knapsack 2000, `maxSolutions 1` + `maxNodes 200` | 10 s | 1 `Optimal` | 2 `Solution Found` | 128151 |

### 2.3 What this means for the contract (measured, not assumed)

- `sol_status == 2` is **not** a timeout/incumbent signal: it appears on
  proven-optimal solves (rows in 2.2).
- `pulp_status == 0` does **not** mean "no numbers": the objective and every
  `varValue` are populated with relaxation values; on set cover they are
  fractional and on both families the objective equals the bound, not a solution.
- Consequently the earlier design assumption ("timeout with incumbent is
  distinguishable as `status==0` and `sol_status==2`") is **wrong for the cases I
  could produce**. The reliable test is our own validation of the returned
  assignment (integrality + exclusivity + window + duration checks) plus the
  solver's own reported bound. A `Not Solved` result must therefore default to
  *no plan*, and may only be surfaced as PARTIAL after we validate it ourselves
  (§9.2).
- I could not force a time-limited stop that carries a valid incumbent even with
  `maxSolutions`/`maxNodes` caps: PuLP reported `Optimal` in those runs. This is
  recorded as an observation, not a guarantee that no CBC build can report
  `Not Solved + Solution Found`.

---

## 3. Item c — protected conflict: conflict + suggested minimal relaxation, never auto-drop

**Design.**

1. Hard-constrain `PROTECTED` behaviours (tier 1), maximise the weighted sum over
   the rest (tier 2). Two tiers only (§9.1).
2. If tier 1 is infeasible, do **not** silently drop a protected item and do not
   return a plan that quietly omits it. Return
   `status = PROTECTED_CONFLICT` (HTTP 422) with:
   - `conflict.protected[]` — the protected items in play;
   - `conflict.conflicting_with[]` — capacity/window/other protected items that
     collide (derived by testing removal of each candidate: `|candidates|` extra
     solves, capped);
   - `relaxations[]` — up to 3 ranked suggestions, each **measured by re-solving**:
     | action | example | cost reported |
     |---|---|---|
     | move to another day/window | "move Gym to 17:00–18:00" | objective delta, displaced sessions |
     | shorten | "Deep Work 90 → 45 min fits" | objective delta |
     | drop one protected item | "drop Gym to keep everything else" | objective delta |
   - `auto_drop: false` and an explicit sentence naming what does not fit.
3. Every relaxation is a *proposal*; applying it is a separate user action that
   creates a new plan revision.

**Why never auto-drop.** §1 shows infeasibility is routine (three of twelve
benchmark instances). Silently dropping a protected item would make "protected"
meaningless and would be indistinguishable from the current behaviour, where the
solver leaves low-impact behaviours out and still reports success.

**Strongest argument against.** Computing suggestions costs up to `k+1` extra
solves on a synchronous endpoint, and the suggestion quality is only as good as the
relaxation ordering heuristic — a bad suggestion ("shorten to 5 minutes") is worse
than no suggestion.

---

## 4. Item d — denominator rule

Definitions, using the committed baseline set `C` (see §5) and, per session,
exactly one of: `completed`, `missed`, `dropped_by_system`, `released_by_user`.

- **`dropped_by_system`** (infeasible on a re-plan, retired by the optimizer,
  behaviour deactivated mid-day): **stays in the denominator** and counts as not
  completed. The system made the promise; it does not get to erase it. Reported
  separately in `system_dropped` so it is visible rather than hidden.
- **`released_by_user`** (explicit "not doing this today" / remove from today):
  **leaves the denominator** and is reported separately in `released`, both as a
  count and as `released_ratio = released / |C|`.
- **`completed`** is the numerator.

```
completion_rate = completed / (|C| - released)
released_ratio  = released / |C|
system_dropped  = count(dropped_by_system)      # reported, not subtracted
```

Guards:
1. If `|C| - released == 0`, report `completion_rate = null`, not `1.0`.
2. Always display `released` next to the rate. A user who releases 9 of 10
   sessions and completes 1 must not read as "100%".
3. `system_dropped` is surfaced as an explicit product failure signal (it should
   be rare; a rising value means the planner is over-promising).
4. Re-planning never re-baselines: the denominator is fixed at the moment defined
   in §5, and re-plans only reclassify sessions.
5. Releasing is allowed only before the session's start (or before completion);
   afterwards it is `missed`. This prevents retroactive denominator shrinking.

**Strongest argument against.** A metric that can be improved by releasing work is
gameable; the `released_ratio` guard mitigates but does not eliminate it.

---

## 5. Item e — three definitions of the committed baseline moment

| # | Baseline moment | How it works | Strengths | Costs/risks |
|---|---|---|---|---|
| 1 | **Solve time** — when the optimizer produces the plan | `C` = sessions of the first run of the day | Zero friction; unambiguous; always exists | Commits the user to a plan they have not seen; an early-morning session may be "committed" before the user wakes; penalises a plan the user would have edited |
| 2 | **User commit time** — explicit "Start my day" / accept | `C` = sessions of the revision the user accepts (sessions already started are included retroactively) | Matches the product promise ("committed plan"); user owns the baseline; enables the refusal story ("here is what I could not fit") | Needs a UI action; users may never press it; sessions before the commit need retroactive inclusion rules |
| 3 | **Plan-local day start** — e.g. 05:00 in the plan's timezone | `C` = sessions of the plan that is current at 05:00 local | No friction; deterministic; aligns with the canonical windows (05:00–24:00) | The baseline can move between 05:00 and the first completion if the user edits; no explicit consent |

**Recommendation:** **(2) with (3) as an automatic fallback.** If the user commits,
the baseline is that revision; if not, the plan current at plan-local day start is
baselined at 05:00 (and can no longer be re-baselined once any session of the day
is completed). (1) alone is rejected because it commits the user to output they
never saw; (3) alone is rejected because the baseline can shift silently.

**Strongest argument against.** Two mechanisms mean two code paths and an
ambiguous "when exactly did this numerator start?", and the fallback quietly
reintroduces (1)'s problem for users who never press the button.

---

## 6. Item f — staged schema

**Stage 1 — now (minimum viable, ships with the session-level metric):**

| change | purpose |
|---|---|
| `scheduled_behaviors.planned_session_id` (uuid, unique, generated once) | stable identity across re-plans |
| `completion_logs.planned_session_id` (+ keep `behavior_id`) | per-session completion; fixes C4 and makes §4 computable |
| `optimization_runs.plan_revision` (int), `committed_at`, `baseline_revision` | which revision was committed (§5) |
| `scheduled_behaviors.retired_revision` (nullable int) | system-dropped sessions stay queryable instead of being deleted |

Stage 1 is additive; no data migration beyond backfilling `planned_session_id`
per existing row and pointing existing completions at the matching session.

**Stage 2 — deferred (identity + revision chain):**
`plans(id, user_id, revision, parent_id, committed_at, baseline)` and
`planned_sessions(id, plan_id, behavior_id, start_period, duration, status,
retired_in_revision)`, with `completion_logs.planned_session_id → planned_sessions.id`.

**Stage 3 — deferred (audit):** immutable snapshot JSON per committed revision, so
past plans can be reconstructed after behaviours are edited or deleted.

**What forces the fuller model:**
1. multi-day plans or carry-forward ("this session moved from Tuesday");
2. per-session editing ("move this one session", "swap these two");
3. analytics that must answer historically *why* a session was dropped vs released
   (§4) after the behaviour itself changed;
4. any need to show a past plan exactly as committed (Stage 3).

Until one of those appears, Stage 1 + a `plan_revision` integer is enough, and the
fuller tables would be speculative complexity.

---

## 7. Item g — brute-force oracle test plan (tiny instances)

Goal: prove the solver returns a true optimum (or a proven infeasible) on instances
small enough to enumerate, so tuning/refactoring cannot silently change the maths.

**Instance generator:** `n_behaviours ∈ {2,3,4,5,6}`; horizon reduced to
`periods = 12` (3 h) or 24; each behaviour restricted to a 2–6 period window
(narrow) or any window (wide); durations fixed to 1–2 blocks; impacts and weights
integers in `[-1, 1]` / `{1,2}` so objective ties are exact.

**Oracle:** enumerate every assignment of blocks to behaviours
(`itertools.product` over each behaviour's allowed start positions, pruning
overlaps), keep those satisfying duration bounds and exclusivity, take
`max(objective)`. With `n ≤ 6` and ≤ 6 candidate starts each this is ≤ 46k
assignments; the whole matrix runs in seconds.

**Assertions per instance:**
1. `solver.objective == oracle.objective` (exact, integers).
2. Returned schedule is legal: no overlap, every block inside the selected window,
   duration within `[min, max]`.
3. No block before period 20 (05:00) for any window.
4. If the oracle has no feasible assignment → solver raises `InfeasibleProblemError`.
5. Determinism: same instance twice → same objective (and same schedule if the
   solver is deterministic).
6. Protected-tier property: with one protected item, the oracle restricted to
   assignments including it matches tier-1 behaviour; if none exists → the solver
   reports a conflict, never a plan missing the protected item (§3).
7. Re-solve property (§8): freeze the first `k` periods, brute-force the remainder,
   and compare with `solve_partial_day` restricted to the same unfrozen set.

**Coverage:** 200 random seeds × the 5 sizes (≈1000 cases), plus one hand-built
case per window boundary (05:00 start, 24:00 end, non-adjacent windows). Mark the
suite `slow`; target < 120 s locally, nightly in CI.

---

## 8. Item h — partial-day re-solve redesign

**Problems in `backend/app/api/v1/schedule.py::partial_reoptimize`:**

1. **Duplication.** The query returns `(ScheduledBehavior, Behavior)` and appends
   one `BehaviorScheduleInput` per *row*, so a behaviour with two sessions becomes
   two independent behaviours: duration bounds and objective credit double.
2. **Wrong clock.** `now = datetime.now(timezone.utc)` is compared against
   `target_date = date.today()` (server-local) and plan-local periods — the freeze
   line is off by the UTC offset outside UTC.
3. **Global freeze.** `earliest_free = max(frozen) + 1` freezes every behaviour up
   to the latest frozen period, so one early session blocks re-planning everything
   before it.
4. **No inactive filter.** The query does not filter `Behavior.is_active`, so a
   deactivated behaviour with a session later today is re-planned.
5. **Status lie.** Non-optimal results are persisted as `"feasible"`, which is not
   an `OptimizationStatus` member (C3).
6. **New independent run** instead of a revision, so completions/metrics do not
   carry over.

**Design.**

1. **Plan-local clock.** Store the plan timezone; convert `now` once into plan-local
   time and derive `current_period` from it; `date.today()` is replaced by
   `plan.local_date`. No mixing of UTC timestamps and local dates.
2. **Session-level freeze.** Freeze each *elapsed session* individually (its periods
   pinned to 1 if completed, 0 if missed; its identity pinned so it cannot move),
   instead of a global per-behaviour cutoff. Future sessions of the same behaviour
   remain free.
3. **One input per behaviour.** Build `BehaviorScheduleInput` per `behavior_id`
   (dedupe), aggregating frozen minutes per behaviour, and carry completed minutes
   forward as already-satisfied duration rather than re-imposing `min_duration`.
4. **Deactivated behaviours (required).** Exclude **future** sessions of
   `is_active = False` behaviours from the re-plan — they must not be rescheduled —
   while their **elapsed** sessions stay frozen exactly like any other elapsed
   session. Deactivation therefore takes effect from the next unfrozen period and
   never rewrites what already happened. The new revision records the exclusion
   (`excluded_behaviors[]`) and the response lists the retired sessions explicitly,
   so the behaviour is auditable rather than a silent disappearance.
5. **Stability term.** Add `λ · disruption` (moved sessions, moved minutes) to the
   objective so the re-solve prefers the smallest sufficient change. `λ` is a
   documented constant, not a user knob; report the disruption count in the
   response so the plan can be explained.
6. **Revision, not fork.** Create `plan_revision + 1` sharing `planned_session_id`s
   (§6 Stage 1), so completions and §4's denominator survive.
7. **Honest status.** Persist the validated outcome: OPTIMAL / FEASIBLE / PARTIAL
   (§9.2) or a structured conflict; never `"feasible"` for a timeout.

**Sequencing:** (a) plan-local clock + dedupe + status — pure correctness;
(b) elapsed-session freeze + deactivated exclusion; (c) stability term;
(d) revisions (depends on §6 Stage 1).

**Strongest argument against.** Freezing elapsed sessions and excluding deactivated
future sessions can make the remainder infeasible (a missed protected session
cannot be rescheduled and the day may have no room), so the correct answer becomes
"your day no longer fits" at exactly the moment users churn. The stability penalty
also makes results harder to explain and adds a constant we cannot calibrate
without usage data.

---

## 9. Cross-cutting decisions

### 9.1 PREFERRED tier — dropped

The agreed design is **two tiers: protected and everything else**, ranked inside
tier 2 by the weighted sum. A third `PREFERRED` tier has no verifiable semantics:
implemented as a weight bonus it is indistinguishable from "a high weight", and
implemented as a constraint it is just a weaker `PROTECTED`. It also doubles the
UI states and makes "why was this scheduled?" unexplainable. Non-protected items
are already ordered by impact, which is the only ordering we can defend with data.
**Decision: `PROTECTED` (boolean or two-value tier) + weighted sum. No PREFERRED.**

### 9.2 PARTIAL vs FEASIBLE

- **FEASIBLE** — the solver ran to its own termination criterion and the returned
  schedule passed our independent validation (integral, no overlaps, inside
  windows, inside duration bounds). Exclusion of items is explained by constraints
  and the objective; optimality was not proven (or the instance is large enough
  that we stop at a gap).
- **PARTIAL** — the solve was **cut short by the time limit** (or another budget),
  the schedule passed the same validation, but we cannot claim it is optimal or
  complete. The response must state: which behaviours were not placed, that a
  retry may place more, and `elapsed_ms`. PARTIAL is FEASIBLE + "stopped early,
  unproven", with a different product meaning (never presented as "your day is
  settled").

This distinction is necessary **because of §2**: PuLP cannot tell us whether a
time-limited solve held a usable solution, so we decide from our own validation and
treat "Not Solved + validated" as PARTIAL, and "Not Solved + not validated" as a
500/504 (no plan), never as success.

### 9.3 Three-distinct-plans candidate set — deferred

Deferred, not rejected. Measured cost is small (~1–3.5 s for N=3 at 40 behaviours,
§1), so cost is not the reason. The reasons are: (i) it conflicts with the
commitment model — a baseline (§5) needs **one** plan to be committed, so
candidates would have to be resolved before commit anyway; (ii) there is no
evidence users want alternatives rather than a better single plan plus §3's
explanation; (iii) no-good cuts need care to avoid returning near-duplicates.
Revisit after cost-to-fit and protected conflicts ship.

---

## 10. Reproduction

```bash
# benchmark (§1) — writes scratch/bench_cbc_results.json
cd backend && uv run python ../scratch/bench_cbc.py

# timeouts (§2)
cd backend && uv run python ../scratch/timeout_probe.py      # no incumbent
cd backend && uv run python ../scratch/timeout_probe4.py     # knapsack sweep
cd backend && uv run python ../scratch/timeout_probe7.py     # set cover, all limits
cd backend && uv run python ../scratch/timeout_probe6.py     # maxSolutions caps
```

Machine: Windows 11, local CPU, PuLP 2.8.0 (bundled CBC), Python 3.12.13. Results
are single-run timings on one machine.

## 11. What I could not determine

- Whether any CBC build reports `Not Solved` + `Solution Found` (§2.2) — not
  observed here; the contract must not depend on it.
- Real-world duration/impact distributions, so §1's sizes are a proxy, not a
  workload model.
- Whether users want alternatives (§9.3) or protection (§3) more; both are design
  bets until there is usage data.
- Production's actual enum/schema state (raised in the migration work) remains
  unverified from here.
