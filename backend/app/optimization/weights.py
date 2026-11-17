"""Objective weights: normalised once, recorded on every plan.

Users edit weights; the solver only ever sees a distribution summing to 1, so
raising one objective's weight cannot inflate every plan's reported value. The
raw and normalised pairs are recorded on the plan for auditability
(docs/FORMULATION.md).
"""

from __future__ import annotations

from typing import Dict, Mapping


def normalise_weights(weights: Mapping[str, float]) -> Dict[str, float]:
    """Return weights scaled to sum to 1.

    Non-positive totals (all weights zero, or only negative ones) fall back to an
    equal split: a plan must still be solvable and explainable.
    """
    raw = {key: float(value) for key, value in weights.items() if value is not None}
    if not raw:
        return {}
    total = sum(raw.values())
    if total <= 0:
        share = 1.0 / len(raw)
        return {key: share for key in raw}
    return {key: value / total for key, value in raw.items()}


def record_weights(weights: Mapping[str, float]) -> Dict[str, Dict[str, float]]:
    """The audit record stored in a plan's diagnostics."""
    normalised = normalise_weights(weights)
    return {
        "raw": {key: round(float(value), 6) for key, value in weights.items()},
        "normalised": {key: round(value, 6) for key, value in normalised.items()},
    }
