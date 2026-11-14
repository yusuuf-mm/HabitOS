# Candidate-placement formulation

The model Phase 3 prototypes and benchmarks. It replaces the block model
(`x[behaviour, period]` binaries) with one binary per **candidate session**, which
makes contiguity structural instead of a post-hoc merge.

Status: prototype only. Production still uses `solver/linear.py`.

## Sets

- `B` — behaviours eligible for the day (active, not already fully elapsed).
- `P` — periods 0..95, 15 minutes each, 00:00–24:00; plan day 05:00–24:00.
- `C_b` — candidate sessions for behaviour `b`: every contiguous run of periods
  inside one allowed window whose length in periods is within
  `[ceil(min_b / 15), floor(max_b / 15)]`.

A candidate is `(b, start, length)`. Candidates are generated, not chosen by the
solver, so a behaviour with a 30–60 minute range and a 4-hour window has ~24
candidates, not 4 hours × 16 lengths.

## Decision variables

- `y[c] ∈ {0,1}` — candidate `c` is selected.
- `z[b] ∈ {0,1}` — behaviour `b` is declined (see §Declines).

## Constraints

1. **At most one session per behaviour**: `Σ_{c ∈ C_b} y[c] + z[b] ≤ 1`.
   With `z[b] = 0` this is `Σ y[c] = 1`; the objective decides whether dropping is
   better than scheduling.
2. **Period exclusivity**: for every period `t`, `Σ_{c ∋ t} y[c] ≤ 1`.
3. **Protected tier first**: for protected behaviours, `Σ y[c] + z[b] = 1`
   (no silent skip). A protected conflict is reported with the smallest relaxation
   that resolves it; it never silently drops a protected behaviour.
4. **Flexible tier**: unprotected behaviours may be declined; `z[b]` carries a
   reason code (`no_fit`, `preempted_by_protected`, `over_capacity`).
5. **Multi-session behaviours** (`sessions_b > 1`): candidates are grouped into
   slots; `Σ_{c ∈ group k} y[c] ≤ 1` per slot, `Σ_k ≤ sessions_b`, and
   `start(c2) − end(c1) ≥ min_gap` for consecutive selected slots
   (`big-M` with the gap bound, or an ordering constraint per pair).
6. **Frozen periods** (partial-day re-solve): candidates overlapping a frozen
   period are removed unless the frozen value came from that same session; a
   session that started is fixed to its remaining length.
7. **Windows / slots**: candidates are generated only inside the behaviour's
   allowed windows, so window feasibility is structural.

## Objective

Maximise the same quantity the current model does (`objective.py`), computed from
the emitted schedule, not from the LP value:

```
Σ_b  Σ_{c ∈ C_b} y[c] · duration(c) · impact(b, objective) · weight(objective)
  −  Σ_b  z[b] · decline_penalty(b)
```

`decline_penalty` is `0` for flexible behaviours (declining is allowed and
reported), and a large constant for protected ones so a decline is only ever a
reported exception. No energy term: energy is dormant (Phase 1 decision).

## Contiguity

A selected candidate is one contiguous session by construction. No merge step, no
"72 sessions for 20 behaviours" artifact. A behaviour that needs to be split
(`sessions_b > 1`) splits into explicit slots with a minimum gap, not into
whatever CBC happens to emit.

## Declines and reasons

`z[b] = 1` means the planner declined the behaviour, never that it forgot it.
Reasons, in order of precedence:

- `no_fit` — no candidate fits the remaining free periods (capacity).
- `preempted_by_protected` — a protected behaviour took the only periods it could use.
- `over_capacity` — total protected demand exceeds the day; the response includes
  the conflicting set and the smallest relaxation (which behaviour, how many
  minutes) that would make it feasible.

The response never omits a protected behaviour silently: it is either scheduled,
or declined once with its reason and the conflict that caused it.

## What the prototype must show

1. Same objective as the block model on the same instances (unit bug removed).
2. Fewer sessions per behaviour, always contiguous.
3. Solve times inside a synchronous budget (≤ ~2 s at 40 behaviours).
4. Agreement with a brute-force oracle on tiny instances, including infeasible,
   over-capacity and protected-conflict cases.
