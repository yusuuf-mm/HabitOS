# Session identity and snapshot schema (stage 1)

What `docs/METRIC.md` needs from the database, and the smallest schema that gives
it. Stage 2/3 of `PART_B_DESIGN.md` §6 (a `plans` table, immutable per-revision
JSON) are **not** part of this change.

## The problem being fixed

Today a session has no identity beyond `(optimization_run_id, behavior_id,
time_period)`. Consequences:

- A completion is attributed to a *behaviour*, so three planned sessions of the
  same behaviour are indistinguishable: any one completion looks like all three.
- Re-planning deletes the previous run's rows, so a session that vanished is
  gone — it cannot be counted as system-dropped, only forgotten.
- There is no record of which revision was the day's committed baseline, so the
  denominator would move every time the user re-planned.

## Columns

### `scheduled_behaviors`

| column | type | null | purpose |
|---|---|---|---|
| `planned_session_id` | uuid, unique | no | stable identity across re-plans and across the completion log |
| `plan_revision` | integer | no, default 1 | which revision of the day produced this session; copied from its run so a session is self-describing |
| `retired_revision` | integer | yes | revision that dropped this session (`dropped_by_system`). `NULL` = still promised |
| `released_at` | timestamptz | yes | when the user released it (`released_by_user`). Only settable before the session starts |

`time_period` and `scheduled_duration` already snapshot *when* and *how long*; the
behaviour's own duration range may change later without altering a promise that
was already made.

### `completion_logs`

| column | type | null | purpose |
|---|---|---|---|
| `planned_session_id` | uuid, references `scheduled_behaviors.planned_session_id` | yes | binds a completion to one session. Nullable only for logs written before this change and for completion of an unscheduled behaviour |

`behavior_id` stays: analytics by behaviour and the existing UI queries use it,
and a completion can exist without a session.

### `optimization_runs`

| column | type | null | purpose |
|---|---|---|---|
| `plan_revision` | integer | no, default 1 | 1 for the first plan of a day, +1 per re-plan |
| `committed_at` | timestamptz | yes | when the user accepted this revision as the baseline |
| `baseline_revision` | integer | yes | the revision whose sessions form `C`; written once and never changed |

## State is derived, not stored twice

A session's metric state is derived from the three facts above:

```
completed          completion_logs.planned_session_id = session.planned_session_id
released_by_user   released_at IS NOT NULL
dropped_by_system  retired_revision IS NOT NULL
missed             none of the above, and the session's window has ended
```

Nothing writes a status enum, so the four states cannot disagree with the
timestamps they are derived from.

## Backfill (upgrade path)

For rows that predate this change:

1. Every existing `scheduled_behaviors` row gets a fresh `planned_session_id`,
   `plan_revision` from its run (default 1), `retired_revision = NULL`,
   `released_at = NULL`.
2. Existing `optimization_runs` get `plan_revision = 1`, `committed_at = NULL`,
   `baseline_revision = NULL`.
3. Every `completion_logs` row with an `optimization_run_id` is pointed at the
   earliest session for the same behaviour in that run. If the run scheduled the
   behaviour more than once, only one completion can be matched; the others stay
   `NULL` rather than inventing a session. A log without a run stays `NULL`.

The backfill runs inside the migration, so a downgrade followed by an upgrade
re-derives it (`planned_session_id` values differ — they are opaque).

## Downgrade

Drops the four new columns, the unique index on `planned_session_id`, the
`completion_logs` foreign key and index, and the three `optimization_runs`
columns. Rows, behaviours, runs and completions themselves are untouched; only
the added identity is lost, which is all that existed before this change.

## What would force stage 2

Multi-day plans, per-session editing ("move this one"), or showing a past day
exactly as it was committed. None of those exist yet, so a `plans` table would be
speculative.
