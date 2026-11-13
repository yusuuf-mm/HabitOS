"""Bounded worker pool for CPU-bound solves.

PuLP/CBC is blocking. Callers on the event loop hand the solve to this pool and
await it, so a long solve cannot stall unrelated requests.

Three properties matter here:

* **No queue.** When every worker is occupied the call is refused immediately with
  :class:`SolverBusyError` (503 + retry hint) instead of waiting behind a backlog.
* **Daemon workers.** A worker stuck inside CBC cannot keep the process alive at
  shutdown, which a ``ThreadPoolExecutor`` would do.
* **No asyncio primitives for admission.** A lock bound to a closed event loop
  would deadlock the next loop; the counter uses a plain ``threading.Lock``.
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
from concurrent.futures import Future
from typing import Any, Callable, TypeVar

from app.core.exceptions import SolverBusyError, SolverTimeoutError

logger = logging.getLogger(__name__)

MAX_SOLVER_WORKERS = 2
# Grace period on top of the solver's own time limit before the await gives up.
TIMEOUT_GRACE_SECONDS = 5

_Job = tuple[Callable[..., Any], tuple, dict, Future]

_jobs: "queue.Queue[object]" = queue.Queue()
_workers: list[threading.Thread] = []
_workers_lock = threading.Lock()

# Admission control, not a queue: an occupied slot means "try again shortly".
_active = 0
_state_lock = threading.Lock()

T = TypeVar("T")


def _worker() -> None:
    while True:
        job = _jobs.get()
        if job is None:
            return
        fn, args, kwargs, future = job  # type: ignore[misc]
        try:
            if not future.set_running_or_notify_cancel():
                continue
            future.set_result(fn(*args, **kwargs))
        except BaseException as exc:  # noqa: BLE001 - forwarded to the awaiter
            future.set_exception(exc)
        finally:
            _jobs.task_done()


def _ensure_workers() -> None:
    with _workers_lock:
        while len(_workers) < MAX_SOLVER_WORKERS:
            thread = threading.Thread(
                target=_worker, name=f"solver-{len(_workers)}", daemon=True
            )
            thread.start()
            _workers.append(thread)


def _try_acquire_slot() -> bool:
    global _active
    with _state_lock:
        if _active >= MAX_SOLVER_WORKERS:
            return False
        _active += 1
        return True


def _release_slot() -> None:
    global _active
    with _state_lock:
        if _active > 0:
            _active -= 1


def active_solves() -> int:
    """Number of solves currently holding a slot (for tests and diagnostics)."""
    return _active


async def run_in_solver_pool(
    fn: Callable[..., T],
    *args: Any,
    timeout_seconds: float,
    **kwargs: Any,
) -> T:
    """Run a blocking solve in the bounded pool, bounded by *timeout_seconds*.

    Raises :class:`SolverBusyError` immediately when no worker is free, and
    :class:`SolverTimeoutError` when the solve outlives its limit.
    """
    if not _try_acquire_slot():
        raise SolverBusyError(
            "Solver is busy",
            detail=(
                f"{MAX_SOLVER_WORKERS} of {MAX_SOLVER_WORKERS} solver workers are "
                "in use; retry in a moment"
            ),
        )

    _ensure_workers()
    try:
        future: Future = Future()
        _jobs.put((fn, args, kwargs, future))
        wrapped = asyncio.wrap_future(future)
        return await asyncio.wait_for(
            wrapped, timeout=timeout_seconds + TIMEOUT_GRACE_SECONDS
        )
    except asyncio.TimeoutError as exc:
        logger.warning("Solve exceeded %.1fs in the worker pool", timeout_seconds)
        raise SolverTimeoutError(
            f"Solver did not finish within {int(timeout_seconds)} seconds"
        ) from exc
    finally:
        _release_slot()


def shutdown_pool() -> None:
    """Stop accepting work. Called on application shutdown."""
    with _workers_lock:
        for _ in _workers:
            _jobs.put(None)
        _workers.clear()
