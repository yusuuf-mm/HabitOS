# Completion rate — v1 (amended, pre-release)

**Status:** current definition, version 1. Amended in place before any code
depended on it; there is no v0 to be compatible with. Any later change bumps the
version and adds a row to the changelog.

The metric answers one question: *of the sessions the planner promised for a day,
how many did the user actually do?* It is deliberately not "how many behaviours
did you complete" — a behaviour split into three sessions is three promises.

## Terms

- **Baseline set `C`** — the sessions promised by the day's baseline plan (§2).
  Every rate is computed against `C`, never against the plan on screen now.
- **Session** — one row of `scheduled_behaviors`: a behaviour, a start period, a
  duration, and a stable `planned_session_id`.
- **Session state** — exactly one of `completed`, `released_by_user`,
  `dropped_by_system`, `missed` (§3).
- **Plan revision** — `optimization_runs.plan_revision`. Revision 1 is the first
  plan of the day; a real re-plan of a frozen baseline is the next revision.
  Runs produced before the baseline freezes are **drafts**, not re-plans: they
  are revision 1, they retire nothing, and they cannot create dropped sessions.

## 1. The rate

```
completion_rate        = completed / (|C| - released)
released_ratio         = released / |C|
system_dropped         = count(dropped_by_system)          # reported, not subtracted
completion_rate_vs_feasible = completed / (|C| - released - dropped_by_system)
```

- `completed` counts **sessions**, not minutes: duration is the solver's choice,
  and counting minutes would let one long session outweigh three short ones.
- `released` leaves the denominator because the user withdrew the promise. It is
  always displayed next to the rate as a count and as `released_ratio`.
- `dropped_by_system` stays in the denominator. The planner made the promise; a
  re-plan that cannot fit a session does not get to erase it. It is reported
  separately, because a rising value means the planner is over-promising.
- `completion_rate_vs_feasible` is the second, contextual figure (§6).

## 2. Baseline moment

The baseline is the plan the user accepted, or — if they never accepted one — the
plan that was current when the day committed itself. Concretely:

1. **Explicit commit.** `POST /schedule/commit` records the run as the baseline
   (`baseline_revision = plan_revision`, `committed_at` set).
2. **Open period.** The baseline stays open for re-commit until the later of:
   the first session of the plan starting, or 05:00 plan-local. Until then the
   day's runs are drafts and committing replaces the baseline freely.
3. **Freeze.** Once that moment passes, the baseline is frozen and cannot be
   re-committed. If a plan exists, the baseline is the plan current at the freeze
   moment. If no plan existed at 05:00, the baseline is the first plan committed
   that day, or, if none is ever committed, the plan current when its first
   session starts.
4. **Exactly one baseline per day.** A day may have many runs; at most one is
   the baseline, and `baseline_revision` is written once.

## 3. Session states

Precedence, highest first:

### 3.1 `completed`
A completion log names the session (`completion_logs.planned_session_id`). A
completion counts if it is logged **at any time before the local day ends**, even
after the session's window — that is a late completion, counted as completed and
flagged `late` so the UI can say so. Logs after the local day ends do not count.
One completion counts once per session.

### 3.2 `released_by_user`
Either:
- the user explicitly releases the session (`POST /schedule/{id}/release`,
  `released_at` set), possible only before it starts; or
- the user deactivates its behaviour before the session starts (§3.3 of the
  amendments — the user withdrew the plan, the planner did not fail).

Releasing after the start time is not a release: the session is `missed`. This
blocks retroactive denominator shrinking. Released sessions leave the denominator
and are reported as `released` and `released_ratio`.

### 3.3 `dropped_by_system`
The session was in `C` and a later revision retired it: it became infeasible, or
the planner could not fit it. Recorded as `scheduled_behaviors.retired_revision`.
Rows are never deleted and never renumbered, so this stays countable. It remains
in the denominator and is reported separately.

### 3.4 `missed`
The session's window ended without a completion and without a release.

### 3.5 Deactivated behaviours
Deactivating a behaviour affects future sessions only: its sessions that have not
started are released (3.2), its elapsed sessions stay in `C` exactly as they were.
A re-plan never deletes or renumbers a session that already belongs to `C`.

## 4. Re-planning

Re-planning a frozen baseline creates a run with `plan_revision = previous + 1`:

- Sessions that survive keep their `planned_session_id`, even if they moved.
- Sessions the new plan no longer contains get `retired_revision` set; they stay
  in `C` and become `dropped_by_system`.
- Sessions added after the baseline are **not** in `C`; they are reported as
  `added_after_baseline` and excluded from both numerator and denominator.
- The denominator therefore **never shrinks** from re-planning. It can only
  shrink because the user released a session.
- Re-solving before the baseline freezes (a draft) changes nothing in `C`: draft
  runs are revision 1, they retire no session, and the baseline will be whichever
  draft is current when the baseline freezes.

## 5. Timezone and day boundaries

The user's timezone is stored on `users.timezone` (IANA name, e.g.
`Europe/Berlin`; defaults to `UTC`). It drives:

- the plan-local day boundary, including the 05:00 baseline hour;
- which day a session belongs to (the day its start period falls in);
- the local day end used for late completions;
- "current period" and start-time checks for releasing.

All stored instants remain UTC; only the interpretation is local.

## 6. Known tension: a re-plan can only lower the strict rate

Fixing `C` at the baseline means a re-plan that drops an infeasible session
leaves it in the denominator, so the strict rate can only go down as the planner
corrects itself. That is deliberate: a planner should not be able to improve its
own score by giving up on promises, and a user should be able to see that three
sessions were dropped by the system rather than by them.

It is also unfair to read alone, which is why the UI shows a **second figure**:

```
completion_rate_vs_feasible = completed / (|C| - released - dropped_by_system)
```

Sessions done out of what remained feasible after each re-plan. The strict rate
stays the headline; the second figure is context, never a replacement, and the
dropped count is always visible next to both.

## 7. Weekly and multi-day rates

Multi-day rates are computed from **summed counts**, never as an average of daily
percentages:

```
rate(days) = sum(completed) / sum(|C| - released) over those days
```

A day with 1 session completed and a day with 1 of 10 completed is 2/11 ≈ 18%,
not (100% + 10%) / 2 ≈ 55%. Days with no baseline contribute nothing (their
`|C| = 0`), and `null` is returned only when the summed denominator is zero.

## 8. Guards and edge cases

1. Denominator `|C| - released == 0` → `completion_rate = null` (not `1.0`, not
   `0.0`), with `released_ratio = 1.0`. "You released everything" is not "you
   finished".
2. A day with no plan has `|C| = 0` → `null`.
3. A day whose baseline has not frozen yet has no `C`; its rate is `null` and its
   status is reported as `open`, never as a perfect or failing day.
4. Sessions added after the baseline are excluded from both numerator and
   denominator.
5. Minutes are reported alongside (`completed_minutes / planned_minutes`) for
   context only; they never change the rate.
6. Rounding is display-only: store and compare the exact ratio, show whole
   percentages.

## 9. What this metric is not

- It does not measure plan quality. An easy plan scores well; a demanding one
  abandoned halfway scores badly even if the planning was good.
- It does not reward partial completion of a session.
- It is gameable by releasing. `released_ratio` is the mitigation, not a fix.

## 10. Commitments and deadlines (items)

Commitments are **context, not sessions**: they occupy time (blocked periods
the solver plans around, `POST /items/preview` shows the cost) but they never
enter the completion-rate denominator — neither as baseline sessions nor as
completions. A commitment that displaces a habit mid-day shows up only through
the normal mechanism: the habit session is released or dropped by the system
and the rate keeps its two small numbers. Commitments are reported separately
(as blocked periods in solver diagnostics and the preview's displaced list),
never merged into `completed`/`baseline` counts.
Deadlines follow the same rule: a deadline is a reminder, not a session, and
is likewise excluded from the denominator. If a deadline ever gains a
preparation block that the planner places, that prep session counts normally —
but Step 1 stores no prep sessions, so deadlines stay fully out of the metric.

## 11. Week planning (preview/apply)

`POST /optimization/week/preview` never writes. It solves each plannable date
with the same problem builder, saved objective weights and commitment blocks as
a normal day solve, then returns real per-date `added` / `moved` / `dropped`
sessions against the plan currently shown. A date that cannot be planned is
reported as `available: false` with a reason; it is never rendered as zero
changes. Past dates are read-only and appear as unavailable rows.

`POST /optimization/week/apply` rechecks the preview's input fingerprint,
re-runs the same solves and writes every date in one transaction; any failure
rolls the whole week back. A frozen today is a partial re-plan at the next
revision and carries its session identities; future dates are ordinary new day
plans. Nothing here commits a future baseline or changes the denominator:
future drafts still have no `C` until their own baseline freezes (§2).

## Changelog

| version | change |
|---|---|
| v1 (week planning) | Explicit seven-day preview/apply: write-nothing preview, fingerprinted all-or-nothing apply, frozen-today partial re-plan, and unavailable states instead of empty data. |
| v1 | Session-level denominator frozen at the baseline moment; released sessions leave and are reported; system-dropped sessions stay and are reported separately; re-planning never shrinks the denominator. |
| v1 (amended) | Baseline open until first session start or 05:00 local, whichever is later; drafts are not re-plans. Deactivating a behaviour before a session starts counts as released. Late completions (before local day end) count and are flagged. Timezone stored per user and used for boundaries. Multi-day rates are summed, not averaged. Known-tension section and `completion_rate_vs_feasible` added. |
| v1 (items) | Commitments are context, not sessions: excluded from the completion-rate denominator, reported separately; deadlines likewise unless a prep block becomes a session. |
