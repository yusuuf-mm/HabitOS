"""Route-level contract: what the solve endpoint returns for every failure.

- infeasible / timeout -> 422 with an explanation the user can act on
- busy pool            -> 503 with a retry hint
- unexpected failure   -> 500 with generic text, no internal detail
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

import app.api.v1.optimization as optimization_routes
from app.core.exceptions import (
    InfeasibleProblemError,
    SolverBusyError,
    SolverTimeoutError,
    UnboundedProblemError,
)


async def _create_behavior(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/behaviors",
        json={
            "name": "Work",
            "category": "productivity",
            "durationMin": 30,
            "durationMax": 60,
            "preferredTimeSlots": ["flexible"],
        },
    )
    assert response.status_code in (200, 201), response.text


def _patch_solver(monkeypatch, exc: Exception) -> None:
    class _FailingSolver:
        def __init__(self, *args, **kwargs):
            pass

        def solve(self, problem, optimization_run_id):
            raise exc

    monkeypatch.setattr(optimization_routes, "LinearSolver", _FailingSolver)


@pytest.mark.asyncio
async def test_infeasible_solve_returns_422_with_explanation(auth_client: AsyncClient, monkeypatch):
    await _create_behavior(auth_client)
    _patch_solver(monkeypatch, InfeasibleProblemError("No plan satisfies the current constraints"))

    response = await auth_client.post("/api/v1/optimization/solve", json={})

    assert response.status_code == 422, response.text
    assert "No plan satisfies" in response.json()["detail"]

    # Nothing was stored, so the previous plan (if any) still stands.
    history = await auth_client.get("/api/v1/optimization/history")
    assert history.json()["data"]["total"] == 0


@pytest.mark.asyncio
async def test_timeout_returns_422_with_explanation(auth_client: AsyncClient, monkeypatch):
    await _create_behavior(auth_client)
    _patch_solver(
        monkeypatch,
        SolverTimeoutError("Solver did not reach optimality within 30 seconds"),
    )

    response = await auth_client.post("/api/v1/optimization/solve", json={})

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert "did not reach optimality" in detail
    assert "30" in detail


@pytest.mark.asyncio
async def test_unbounded_returns_422(auth_client: AsyncClient, monkeypatch):
    await _create_behavior(auth_client)
    _patch_solver(monkeypatch, UnboundedProblemError("The problem is unbounded"))

    response = await auth_client.post("/api/v1/optimization/solve", json={})

    assert response.status_code == 422
    assert "unbounded" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_busy_solver_returns_503_with_retry_hint(auth_client: AsyncClient, monkeypatch):
    await _create_behavior(auth_client)

    async def _busy(*args, **kwargs):
        raise SolverBusyError(
            "Solver is busy",
            detail="2 of 2 solver workers are in use; retry in a moment",
        )

    monkeypatch.setattr(optimization_routes, "run_in_solver_pool", _busy)

    response = await auth_client.post("/api/v1/optimization/solve", json={})

    assert response.status_code == 503, response.text
    assert response.headers.get("Retry-After") == "2"
    assert "retry" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_unexpected_solver_failure_is_a_500_without_internal_text(
    auth_client: AsyncClient, monkeypatch
):
    await _create_behavior(auth_client)
    _patch_solver(monkeypatch, RuntimeError("boom: /srv/app/hidden/path.py line 42"))

    response = await auth_client.post("/api/v1/optimization/solve", json={})

    assert response.status_code == 500, response.text
    body = response.json()
    assert body["detail"] == "Optimization failed"
    assert "boom" not in response.text
    assert "hidden" not in response.text
