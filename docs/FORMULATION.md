# Candidate-placement formulation

The model the planner runs. It replaced the block model (`x[behaviour, period]`
binaries) with one binary per **candidate session**, which makes contiguity
structural instead of a post-hoc merge.

- Shipped: `app/optimization/solvers/candidate.py` (`CandidateSolver`).
- Prototype and benchmarks: `tools/candidate_model.py`,
  `tools/bench_candidate_v2.py`, `tools/oracle_compare.py`.
- The block model remains at `app/optimization/solvers/linear.py` as the
  reference the candidate model was checked against; no route builds it.

Both models satisfy the same contract: `solve(problem, run_id) ->
OptimizationSolution`, `validate_schedule` before anything is returned, the value
defined once in `objective.py`, and the solve running in the bounded worker pool.

## Size limits

- **25 active behaviours per plan.** Above that the solve is refused with a clear
  message ("the planner accepts up to 25… deactivate some, or split the day")
  instead of silently truncating or timing out. The route returns that message as
  a 422.
- **Duration step.** Each behaviour contributes at most 8 candidate lengths,
  always including its minimum and maximum.
- **Start alignment.** When a duration is a multiple of 30 minutes, candidate
  starts are aligned to 30 minutes; an odd number of 15-minute periods keeps every
  start, because aligning it would move the end off the half hour.
- **Time limit** comes from `OPTIMIZATION_TIMEOUT_SECONDS` and is passed to CBC;
  the pool's grace period is separate.

## Sets

- `B` — behaviours eligible for the day: every active behaviour with
  `min_duration > 0`.
- `P` — periods 0..95, 15 minutes each, 00:00–24:00 (plan day 05:00–24:00).
- `W_b` — the behaviour's allowed windows: the contiguous ranges of the periods
  covered by its canonical time slots (`early_morning` … `night`, `flexible`).
- `C_b` — candidate sessions for behaviour `b`: every contiguous run of periods
  inside one window of `W_b`, starting no earlier than the first free period, whose
  length in periods is one of `duration_options(min_b, max_b)`.
- `F_b` — the periods of `b` that are already elapsed and frozen.

A candidate is `(b, start, length)`. Candidates are generated, not chosen by the
solver, so the model never sees a fragment.

## Decision variables

- `y[c] ∈ {0,1}` — candidate `c` is selected.
- `z[b] ∈ {0,1}` — behaviour `b` is declined (see §Declines).

## Constraints

1. **Scheduled or declined, never silent, never both**:
   `Σ_{c ∈ C_b} y[c] + z[b] ≤ 1` and `Σ_{c ∈ C_b} y[c] + z[b] ≥ 1`.
   The first form is what makes a multi-session behaviour (`sessions_b > 1`)
   correct: with a plain `≤ sessions_b` a behaviour could be scheduled *and*
   declined at once. The second forbids forgetting a behaviour, which is the one
   outcome declines exist to prevent.
2. **Period exclusivity**: for every period `t`, `Σ_{c ∋ t} y[c] ≤ 1`.
3. **Windows**: candidates are generated only inside `W_b`, so window feasibility
   is structural rather than a constraint CBC could violate.
4. **Frozen periods** (re-plan): every period before the current one is fixed to
   its recorded value. Frozen minutes count towards the behaviour's duration
   bounds, so the remaining candidate is sized to `[min_b − frozen_b,
   max_b − frozen_b]`; a behaviour with nothing left to place is declined instead
   of silently shortened. Frozen runs are re-emitted as schedule items exactly as
   they were.
5. **Daily time budget** (`time_budget` constraint): scheduled minutes, frozen
   plus planned, never exceed `max_daily_minutes`.
6. **Frequency** (`frequency` constraint): the total scheduled periods of a
   behaviour, frozen plus planned, stay inside `[min_frequency, max_frequency]`.
7. **Forced include**: a forced behaviour gets `z[b] = 0` and `Σ y[c] = 1`; if it
   has no candidate at all the solve is infeasible with a message naming it.

There is no protected tier in the shipped model: every active behaviour may be
declined, and the reason is always reported. The prototype's protected/protected-
conflict experiments remain in `tools/candidate_model.py` for the oracle.

## Objective

```
Σ_b Σ_{c ∈ C_b} y[c] · duration(c) · impact(b, objective) · weight(objective)
  −  Σ_b z[b] · decline_penalty(b)
```

`decline_penalty(b) = max(0, score(b)) · min_duration(b) + 0.001`, so declining
costs at least what the shortest session would have earned, plus a tie-break that
places a zero-value behaviour when there is room. A behaviour with negative net
value is declined on purpose.

That penalised quantity is what the solver maximises, but it is **not** the value
of the plan. The value reported to users is the placement value of the emitted
sessions — the same `objective.py` definition Phase 1 introduced:

```
reported value = Σ emitted session minutes × impact × weight
```

The penalised LP value is reported separately as `diagnostics.solver_objective`,
so a decline penalty can never leak into a user-facing number.

## Weights

Users edit objective weights (`PUT /api/v1/behaviors/objectives/{id}`). The set is
stored and always renormalised to sum to 1, so raising one objective lowers the
others instead of inflating every plan's value. The solver only ever receives the
normalised distribution, and each plan records both the weights it was given and
the normalised weights it used:

```json
"diagnostics": {
  "objective_weights": {
    "raw": {"health": 3.0, "learning": 1.0},
    "normalised": {"health": 0.75, "learning": 0.25}
  }
}
```

All-zero weights fall back to an equal split rather than making the plan value
zero.

## Declines and reasons

`z[b] = 1` means the planner declined the behaviour, never that it forgot it.

- `no_fit` — no candidate fits the remaining free periods.
- `over_capacity` — candidates exist, but every one of them overlaps periods other
  sessions took: the day is full.
- `preempted_by_protected` — only reachable in the prototype's protected tier;
  the shipped model never emits it.

The reason is computed after the solve from the emitted schedule, so it describes
the plan the user actually receives. Every plan lists its declines in
`diagnostics.declines` with `behaviorId`, `behaviorName` and `reason`.

## Forced include ("what would it cost to fit X")

`POST /api/v1/optimization/forced-include` runs two solves on the same problem: a
baseline solve and a solve with the requested behaviours forced in. It returns

- `fits` and the forced sessions (start, end, duration),
- `displaced`: the sessions that had to give way, with their reason and minutes,
- `objectiveChange`: forced plan value − baseline plan value,
- `relaxations`: the concrete changes needed (a displaced session, a shortened
  session, or `no_free_window` when the behaviour cannot be placed at all),
- `solverObjective`: the penalised value, for diagnostics only.

These solves run at lower priority in the worker pool: a what-if call never takes
the last worker, so it cannot make the day's real solve wait. It also never
persists a run.

## Diagnostics

Every plan carries:

| key | meaning |
|---|---|
| `formulation` | `candidate` |
| `solver_status` / `solve_status` | CBC status and the contract status |
| `candidate_count` | candidate binaries in the model |
| `session_count` | sessions emitted |
| `plan_value` | placement value, equal to `total_objective_value` |
| `solver_objective` | penalised LP value (diagnostics only) |
| `declines`, `declines_count` | reason codes per declined behaviour |
| `objective_weights` | raw and normalised weights used |
| `frozen_periods_count`, `earliest_free_period` | present only on a re-plan |

`optimization_runs.solver` is a coarse enum column (`linear`, `heuristic`, …) and
stays `linear`; the formulation is recorded in `results.solver` and in
`diagnostics.formulation`.

## Evidence

The gate that cleared this formulation for production (`PHASE_REPORT.md`,
Phase 3):

- like-for-like against the block model: identical value on every instance both
  can solve, no case where the candidate is higher;
- every decline explained by capacity or a window, none with free capacity and
  positive value;
- all ≤20-behaviour instances optimal in under 2 s, 21–25 optimal within 3.1 s,
  above the cap refused;
- 1,000 brute-force oracle instances, 0 objective disagreements, 0 validation
  violations, plus 100 canonical instances clean under the production
  `validate_schedule`.
