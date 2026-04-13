"""Explicit reward/risk ratio math for structure quality."""

from __future__ import annotations


def validate_rr_inputs(max_profit: float, max_loss: float) -> None:
    """Raise clear errors if RR inputs are invalid."""
    if max_profit <= 0:
        raise ValueError("max_profit must be > 0")
    if max_loss <= 0:
        raise ValueError("max_loss must be > 0")


def reward_risk_ratio(max_profit: float, max_loss: float) -> float:
    """Return reward/risk ratio as max_profit / max_loss."""
    validate_rr_inputs(max_profit, max_loss)
    return max_profit / max_loss
