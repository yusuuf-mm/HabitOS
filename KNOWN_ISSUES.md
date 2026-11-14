# Known issues

## KI-001: Some integration-test subsets hang instead of finishing

**Status:** open — reproduced, not fixed. Re-checked 2026-11-14 after the solver
pool moved to daemon threads with a `threading.Lock`: the reproduction below still
prints `2 passed in 4.76s` and then fails to exit (killed at 120 s). The pool is
therefore not the cause; the hang happens after the summary is printed.

**Reproduction (from `backend/`):**

```bash
uv run pytest tests_integration/test_solver_math.py tests_integration/test_behavior_updates.py -q
```

Observed: the process does not exit within 240 s (killed by the caller). The same
modules finish normally when the whole suite runs.

**Other observed shapes:**

- `uv run pytest tests_integration/test_behaviors.py tests_integration/test_analytics.py -q` — hangs (>240 s).
- `uv run pytest tests_integration/test_behaviors.py -q` — passes in ~10 s.

**What still works:**

```bash
cd backend && uv run pytest -q          # 47 passed, 1 xpassed, ~47 s
```

**Impact:** full-suite runs and single-module runs are usable; ad-hoc multi-module
subsets are not reliable, which makes bisecting failures awkward.

**Not yet determined:** whether the stall is in test teardown (event-loop/session
finalisation when only some integration modules import the app), in the
`pulp`/CBC subprocess, or in the shared in-memory SQLite engine (`StaticPool`).
Nothing has been changed to work around it.
