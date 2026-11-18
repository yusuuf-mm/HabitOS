# Items: habits, commitments, deadlines

The planner knows one kind of thing: a flexible habit with a duration range and
preferred windows. People describe days as messier than that:

> "a deadline on 16 November I mustn't forget; take my father to the hospital
> every morning at 8 for 3 days; a new workout at 8 pm"

That is three different objects. This note fixes what the app stores, what the
solver sees, and what the assistant hands over. It is a design, not an
implementation.

## Three kinds

| kind | time | repeats | planner's job |
|---|---|---|---|
| **habit** | flexible duration in preferred windows | daily while active | place it |
| **commitment** | fixed start **and** fixed duration | date range, or weekdays, or every day for N days | treat as occupied, plan around it |
| **deadline** | a date (no time) | no | surface it, remind, optionally reserve preparation time |

The distinction that matters is *who chooses the time*. The planner chooses for
habits; the world chooses for commitments; a deadline has no duration at all.

## Schema: additive columns on `items`, not a new table per kind

**Recommendation: one `items` table with a `kind` column and nullable columns per
kind.** Habits migrate into it unchanged (`kind='habit'`); the existing
`behaviors` table is not dropped in the first step — `items` gets a
`behavior_id` pointer for habit rows, so history and completions keep working
while the planner reads one table.

Why one table: the day view, the metric and the solver all iterate "the things
this day contains". One table means one query and one sort key
(`starts_at`, null for habits). Three tables would force a union in every one of
those places, and the completion-rate denominator would have to merge three
sources every time it is computed.

Columns (all nullable except `kind`, `user_id`, `title`):

| column | kind | meaning |
|---|---|---|
| `kind` | all | `habit` \| `commitment` \| `deadline` |
| `title`, `notes` | all | what the user typed |
| `behavior_id` | habit | the existing behaviour row (impacts, durations, windows) |
| `starts_at` | commitment | timestamptz, plan-local date + time, fixed |
| `duration_minutes` | commitment | fixed, not a range |
| `recurrence` | commitment | `once` \| `daily` \| `weekdays` \| `weekly` |
| `recurrence_until` | commitment | inclusive last date; `limited_run_days` derives it |
| `weekdays` | commitment | bitmask for `weekdays`/`weekly` |
| `due_on` | deadline | date, no time |
| `prep_minutes` | deadline | optional preparation block length |
| `prep_lead_days` | deadline | how many days before `due_on` the prep block may sit |
| `reminder_offsets` | deadline | minutes before `due_on` 09:00 (e.g. `[10080, 1440, 60]`) |

**The strongest argument against it:** nullable columns let invalid combinations
exist — a deadline with a `starts_at`, a commitment with `due_on`, a habit with
both. A table per kind makes those states unrepresentable. The answer is a
`CHECK` constraint per kind plus Pydantic validation at the edge; that costs one
constraint and keeps the single-table read path. A side table for recurrence
rules is the next step if recurrence grows beyond "daily for N days".

## How commitments enter the solver

As **blocked periods, not decision variables**. Each occurrence is resolved for
the target date into `[start_period, end_period)` and merged with the day's other
occupied periods (sleep window, frozen sessions) before candidate generation.
Candidates that overlap a commitment are never created, so the solver cannot
move a hospital appointment, and there is no binary whose value could be "0"
because the appointment was inconvenient.

This is deliberately the same mechanism as frozen periods: the solver's job is
the free time between them. A commitment is not a `BehaviorScheduleInput`, it
does not consume the 25-behaviour cap, it is never declined, and it is never
scored.

What the user sees: commitments are rendered on the day as fixed blocks, visually
distinct from sessions, and they do not move when the day is re-planned.

## Do commitments count in the completion rate?

**Recommendation: no — they are context, not sessions.** METRIC.md §1 defines the
baseline as the plan's sessions and the rate as completions over that baseline. A
hospital appointment was not the planner's proposal, so counting a missed one as
a missed habit would blame the plan for the world. Counting them as completed
would inflate the rate without the user doing anything.

Two consequences, both already supported by the metric:

- A commitment makes the day *harder*, so the "handled the day" figure
  (`completion_rate_vs_feasible`, which excludes what the system dropped) is the
  honest denominator: it already removes sessions the planner could not fit.
- If a commitment displaces a habit mid-day, that habit is released or dropped
  like any other system drop, and the rate keeps its two small numbers.

Deadlines follow the same rule: a deadline is a reminder, not a session. If the
deadline has a preparation block, the prep block *is* a habit-like session and
counts normally, because the planner chose where to put it.

## How a limited run expires

"Every morning at 8 for 3 days" is one commitment row with
`recurrence='daily'`, `recurrence_until = first_date + 2 days`. That is the whole
mechanism: expansion for a target date either yields an occurrence or nothing.
No background job retires it, so there is no state that can be missed while the
app is closed.

- Past `recurrence_until` the commitment simply stops producing occurrences; the
  row stays for history and can be edited.
- The day view shows "last one" on the final date.
- Deleting the commitment mid-run stops future occurrences and leaves already
  materialised days untouched.
- Weekday recurrences (`weekdays`) mean Monday–Friday; a holiday is a future
  feature, not a silent skip.

## How reminders are represented

`reminder_offsets` is a list of minutes before the item's anchor, coarse on
purpose: deadline → `due_on` at 09:00 plan-local; commitment → `starts_at`.
Stored, not scheduled. A delivery layer (push/email) reads the list, and the
`reminder_log` side table records `(item_id, offset_minutes, sent_at)` so a
restart cannot send twice.

No offset in the past is emitted: if the app opens after a reminder's time, the
deadline is shown as due/overdue instead of firing a stale notification.

## What the AI helper hands over

The assistant never writes to `items` directly. It returns a draft list in the
same shape the manual form uses, which the UI shows for confirmation:

```json
[
  {"kind": "deadline", "title": "Submit the tax form", "dueOn": "2026-11-16",
   "reminderOffsets": [10080, 1440, 60]},
  {"kind": "commitment", "title": "Take Dad to the hospital",
   "startsAt": "2026-11-16T08:00", "durationMinutes": 90,
   "recurrence": "daily", "runDays": 3},
  {"kind": "habit", "title": "Workout", "preferredTimeSlots": ["evening"],
   "durationMin": 45, "durationMax": 60}
]
```

Rules for the hand-over, so a bad parse cannot corrupt a day:

- `kind` is explicit; the assistant must choose one, never emit a mixed row.
- Times are plan-local wall clock (`2026-11-16T08:00`), not UTC instants; the
  server attaches the user's zone.
- Anything relative ("tomorrow", "next Tuesday") is resolved by the assistant
  against the plan-local date it is given, and the resolved date is what it
  returns — the draft is exactly what will be stored.
- Ambiguity ("every morning at 8 for 3 days" could mean 3 sessions or 3 weeks)
  comes back as a question, not a guess.
- The draft is validated by the same schema as the form: a malformed draft is
  rejected before the user ever sees a save button.

## Amendment (implemented in Step 1)

Step 1 stores **commitments and deadlines only — no habit rows**. The `items`
table keeps its kind `CHECK` to those two kinds; habits stay in `behaviors`
with their objective impacts and completion history. Unifying later would mean
migrating behaviors, impacts, completion foreign keys and solver inputs into
items — deferred until a real need, because the single-table read path in this
note assumed habits migrate, and they did not.

- **Local-time storage.** A commitment stores `start_date` + `start_time` +
  a `timezone` snapshot (plan-local wall clock, not a timestamptz). Periods
  derive from the stored local time; the snapshot is for display.
- **Private-flag semantics.** Private items are hidden from lists/summaries
  but visible in the owner detail view — and they still block solver time.
  Privacy is visibility, not solver behaviour.
- **Overlap/sleep warnings.** Creation warns when the new commitment overlaps
  another own commitment on its start date, and when it falls in the sleep
  window (21:00–05:00).
- **Preview endpoint.** `POST /items/preview` runs a baseline solve and a
  blocked solve with the draft's periods added, reporting `displaced` (minutes
  lost per behaviour) and `dropped` (behaviours with minutes reduced to zero)
  without writing anything.

## What this note does not decide

- Whether habits and commitments share one calendar colour or two.
- Whether a deadline can *reserve* flexible time automatically; the prep block is
  opt-in per deadline.
- Multi-user commitments (a family calendar). The shape above is per-user.
