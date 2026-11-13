# Completion rate — v1

**Status:** current definition, version 1. Any change to a rule below bumps the
version and adds a row to the changelog at the end, so a number shown in the UI
can always be traced back to the rule that produced it.

The metric answers one question: *of the sessions the planner promised for a day,
how many did the user actually do?* It is deliberately not "how many behaviours
did you complete" — a behaviour split into three sessions is three promises.

## Terms

- **Committed baseline set `C`** — the set of sessions promised for one local
  day, frozen at the baseline moment (§2). Every rate is computed against `C`,
  never against the plan that happens to be on screen now.
- **Session** — one row of `scheduled_behaviors`: a behaviour, a start period, a
  duration. It has a stable `planned_session_id` that survives re-planning.
- **Session state** — exactly one of `completed`, `missed`, `dropped_by_system`,
  `released_by_user` (§3).
- **Plan revision** — `optimization_runs.plan_revision`, incremented per user-
  initiated re-plan of the same day. The first plan of the day is revision 1.

## 1. The rate

```
completion_rate = completed / (|C| - released)
released_ratio  = released / |C|
system_dropped  = count(dropped_by_system)          # reported, not subtracted
```

- `completed` is the numerator and counts **sessions**, not minutes, because
  duration is the solver's choice and would let a long session outweigh three
  short ones.
- `released` is subtracted from the denominator because the user withdrew the
  promise (§3.4). It is always displayed next to the rate as a count and as
  `released_ratio`, so "1 of 1" cannot masquerade as a perfect day when nine
  sessions were released.
- `dropped_by_system` is **not** subtracted. The planner made the promise; a
  re-plan that cannot fit a session, or a mid-day deactivation, does not get to
  erase it from the denominator. It is surfaced separately, because a rising
  value means the planner is over-promising.

## 2. The baseline moment

`C` is fixed once per day, at the first of these that happens:

1. **Explicit commit** — the user accepts a revision ("Start my day"). `C` is
   that revision and `optimization_runs.baseline_revision` records it.
2. **Plan-local day start (05:00)** — if the user never commits, the revision
   current at 05:00 local becomes the baseline.

After `C` is frozen it never moves, with one exception: a session the user
starts before the baseline moment is added retroactively, since the user has
plainly begun it.

The baseline is recorded, not recomputed. `committed_at` and `baseline_revision`
are stored on the run so a past day can be re-read even after the user edits or
deactivates behaviours.

## 3. Session states

### 3.1 `completed`
A completion log points at the session (`completion_logs.planned_session_id`).
One session can be completed once; a second log for the same session is ignored
for the metric.

### 3.2 `missed`
The session's window ended without a completion and without a release. Stays in
the denominator.

### 3.3 `dropped_by_system`
The session was in `C` but a later revision retired it: it became infeasible, or
its behaviour was deactivated mid-day. Recorded as
`scheduled_behaviors.retired_revision = <revision that dropped it>`; the row is
kept, never deleted, so it stays countable.

The same applies to a behaviour deactivated after the baseline: its elapsed
sessions remain in `C` frozen as they were; its future sessions are dropped by
the system. Deactivated behaviours are excluded from *future* plans, but their
past promises are still promises.

### 3.4 `released_by_user`
The user explicitly declined the session for today, before it started.
Recorded as `released_at` on the session. Leaves the denominator and is reported
as `released` plus `released_ratio`. Releasing after the start time is not a
release — the session is `missed`, which blocks retroactive denominator
shrinking.

## 4. Re-planning

Re-planning creates a new run with `plan_revision = previous + 1` and is the only
way sessions leave `C`:

- Sessions that survive keep their `planned_session_id` and count the same.
- Sessions removed become `dropped_by_system` with `retired_revision` set.
- Sessions added are in the new plan but **not** in `C`; they are excluded from
  the rate and reported separately as `added_after_baseline`.
- The denominator therefore **never shrinks** from re-planning. It can only
  shrink by the user releasing a session.

## 5. Guards and edge cases

1. `|C| - released == 0` → `completion_rate = null` (not `1.0`, not `0.0`), with
   `released_ratio = 1.0`. "You released everything" is not "you finished".
2. A day with no plan has `|C| = 0` → `completion_rate = null`.
3. Sessions crossing midnight belong to the day their start period falls in.
4. Sessions the solver emitted but that were never part of `C` (added after the
   baseline) are excluded from both numerator and denominator.
5. Minutes are reported alongside as `completed_minutes / planned_minutes` for
   context only. They never change the rate.
6. Rounding is display-only: store and compare the exact ratio, show one decimal
   place.

## 6. What this metric is not

- It does not measure plan quality. A plan that is easy to follow scores well; a
  demanding plan the user abandons halfway scores badly even if the planning was
  good.
- It does not reward partial completion of a session. Half of a 60-minute block
  counts as zero until the completion log exists; `actual_duration` is stored for
  future metrics but is not used here.
- It is gameable by releasing. `released_ratio` is the mitigation, not a fix.

## Changelog

| version | change |
|---|---|
| v1 | First version. Session-level denominator frozen at the baseline moment; released sessions leave and are reported; system-dropped sessions stay and are reported separately; re-planning never shrinks the denominator. |
