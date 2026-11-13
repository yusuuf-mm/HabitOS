"""The solve pool admits a bounded number of solves and passes its limit to CBC."""

from __future__ import annotations

import asyncio
import contextlib
import threading
from datetime import date
from uuid import uuid4

import pytest
from pulp import PULP_CBC_CMD

from app.core.exceptions import SolverBusyError, SolverTimeoutError
from app.optimization import executor
from app.optimization.models import BehaviorScheduleInput, OptimizationProblem
from app.optimization.solvers.linear import LinearSolver


def _problem() -> OptimizationProblem:
    behavior = BehaviorScheduleInput(
        id=uuid4(),
        name="Run",
        min_duration=30,
        typical_duration=30,
        max_duration=30,
        energy_cost=1.0,
        impacts={"health": 1.0},
        preferred_time_slots=["morning"],
    )
    return OptimizationProblem(
        user_id=uuid4(),
        behaviors=[behavior],
        objectives={"health": 1.0},
        constraints=[],
        start_date=date.today(),
        end_date=date.today(),
        time_periods=96,
    )


def test_cbc_receives_the_solver_time_limit(monkeypatch):
    """CBC must stop itself; a pool timeout alone would leave it running."""
    captured: dict = {}

    def _recording_command(**kwargs):
        captured.update(kwargs)
        return PULP_CBC_CMD(timeLimit=kwargs.get("timeLimit", 5), msg=0)

    monkeypatch.setattr(
        "app.optimization.solvers.linear.PULP_CBC_CMD", _recording_command
    )

    LinearSolver(timeout_seconds=7).solve(_problem(), uuid4())

    assert captured.get("timeLimit") == 7


@pytest.mark.asyncio
async def test_busy_pool_refuses_a_third_solve(monkeypatch):
    """Two occupied workers must yield 503-style refusal, not an unbounded queue."""
    release = threading.Event()
    started = threading.Semaphore(0)

    def _blocking_call():
        started.release()
        release.wait(timeout=10)
        return "done"

    tasks = [
        asyncio.create_task(
            executor.run_in_solver_pool(_blocking_call, timeout_seconds=10)
        )
        for _ in range(2)
    ]

    for _ in range(2):
        for _ in range(200):
            if started._value > 0:  # slots are actually held by a worker
                break
            await asyncio.sleep(0.01)
        started.acquire(timeout=1)

    with pytest.raises(SolverBusyError) as excinfo:
        await executor.run_in_solver_pool(_blocking_call, timeout_seconds=10)

    assert excinfo.value.status_code == 503
    assert "retry" in excinfo.value.detail.lower()

    release.set()
    await asyncio.gather(*tasks)

    assert executor.active_solves() == 0


@pytest.mark.asyncio
async def test_pool_timeout_stops_waiting(monkeypatch):
    monkeypatch.setattr(executor, "TIMEOUT_GRACE_SECONDS", 0)

    def _slow():
        import time

        time.sleep(1.5)
        return "late"

    with pytest.raises(SolverTimeoutError):
        await executor.run_in_solver_pool(_slow, timeout_seconds=0.2)

    # The slot is released even when the await gives up.
    for _ in range(100):
        if executor.active_solves() == 0:
            break
        await asyncio.sleep(0.01)
    assert executor.active_solves() == 0
