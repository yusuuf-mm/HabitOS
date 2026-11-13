# tools/

One-off scripts used to measure and verify the planner. They are not part of the
application and nothing imports them. Run them from `backend/` so `app` is
importable, e.g. `cd backend && uv run python ../tools/bench_cbc.py`.

| Script | What it does |
|---|---|
| `bench_cbc.py` | Times the current block-binary MILP on 12 fixed instances (10/20/40 behaviours, fixed/variable durations, narrow/wide windows). Writes `bench_cbc_results.json` next to itself. |
| `bench_candidate.py` | Same 12 instances against a candidate-placement prototype (one binary per contiguous candidate session) and prints both side by side. |
| `audit_slot_windows.py` | Lists the canonical time windows and how many periods each covers. |
| `timeout_probe*.py` | Probes what PuLP/CBC reports (`status`, `objective`, `varValue`) when a solve is cut off by its time limit. Seven variants because the first attempts did not reproduce a stopped solve. |
| `migration_cycle.sh` | Runs upgrade → downgrade → upgrade against a throwaway Postgres container with seeded rows, checking that data survives. Needs Docker and a running container; set `BENCH_DATABASE_URL` (default targets a disposable container on port 55433). |

Notes:

- No real secrets are in these files. The only credential is the throwaway
  `user:password` pair for the disposable Postgres container; `migration_cycle.sh`
  now reads its URL from `BENCH_DATABASE_URL`.
- `bench_*.py` write result JSON next to the script.
- The probe scripts print solver internals on purpose; they are diagnostics, not
  tests.
