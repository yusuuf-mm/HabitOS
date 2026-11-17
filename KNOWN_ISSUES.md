# Known issues

## KI-001: Some integration-test subsets hang instead of finishing

**Status:** fixed 2026-11-17. The shared `StaticPool` engine in
`tests_integration/conftest.py` was never disposed, and aiosqlite 0.22.1 runs
its connection worker on a non-daemon thread (`Thread(...)` with no
`daemon=True`), so the interpreter waited in `threading._shutdown` forever
after the summary printed. A `faulthandler` dump of the hung process showed
exactly that pair: `aiosqlite/core.py _connection_worker_thread` +
`threading._shutdown`. A session-scoped autouse fixture now runs
`engine.dispose()` at the end of the run.

**Verified after the fix (from `backend/`):**

```bash
uv run pytest tests_integration/test_solver_math.py tests_integration/test_behavior_updates.py -q
# 2 passed in 5.72s, process exits (previously hung past 120 s)
uv run pytest tests_integration/test_auth.py -q
# 4 passed, exits (previously also lingered: single modules were affected too)
```

No issue is currently open.
