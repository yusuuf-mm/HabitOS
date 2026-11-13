"""Bounded worker pool for CPU-bound solves.

PuLP/CBC is blocking. Callers on the event loop hand the solve to this pool and
await it, so a long solve cannot stall unrelated requests. The pool is small on
purpose: solves are memory hungry and the API is a single-process deployment.
"""

from __future__ import annotations

import asyncio
import functools
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, TypeVar

from app.core.exceptions import SolverTimeoutError

logger = logging.getLogger(__name__)

MAX_SOLVER_WORKERS = 2
# Grace period on top of the solver's own time limit before the await gives up.
TIMEOUT_GRACE_SECONDS = 5

_POOL = ThreadPoolExecutor(max_workers=MAX_SOLVER_WORKERS, thread_name_prefix="solver")

T = TypeVar("T")


async def run_in_solver_pool(
    fn: Callable[..., T],
    *args: Any,
    timeout_seconds: float,
    **kwargs: Any,
) -> T:
    """Run a blocking solve in the bounded pool, bounded by *timeout_seconds*."""
    loop = asyncio.get_running_loop()
    call = functools.partial(fn, *args, **kwargs)
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(_POOL, call),
            timeout=timeout_seconds + TIMEOUT_GRACE_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        logger.warning("Solve exceeded %.1fs in the worker pool", timeout_seconds)
        raise SolverTimeoutError(
            f"Solver did not finish within {int(timeout_seconds)} seconds"
        ) from exc


def shutdown_pool() -> None:
    """Stop accepting work. Called on application shutdown."""
    _POOL.shutdown(wait=False, cancel_futures=True)
