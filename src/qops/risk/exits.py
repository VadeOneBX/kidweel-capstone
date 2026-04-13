"""Deterministic exit policy helpers."""

from __future__ import annotations

import math


def take_profit_target(max_profit: float, take_pct: float = 0.80) -> float:
    """Return the take-profit PnL target as a fraction of max profit."""
    if not math.isfinite(max_profit) or max_profit <= 0.0:
        raise ValueError("max_profit must be finite and > 0")
    if not math.isfinite(take_pct) or take_pct <= 0.0:
        raise ValueError("take_pct must be finite and > 0")
    return take_pct * max_profit


def debit_stop_loss(max_loss: float, stop_pct: float = 1.00) -> float:
    """Return the stop-loss PnL threshold as a fraction of max loss."""
    if not math.isfinite(max_loss) or max_loss <= 0.0:
        raise ValueError("max_loss must be finite and > 0")
    if not math.isfinite(stop_pct) or stop_pct <= 0.0:
        raise ValueError("stop_pct must be finite and > 0")
    return stop_pct * max_loss


def time_exit_rule(dte: int, min_dte_to_hold: int = 3) -> str:
    """Return a deterministic time-exit label."""
    if dte < 0:
        raise ValueError("dte must be >= 0")
    if min_dte_to_hold < 0:
        raise ValueError("min_dte_to_hold must be >= 0")
    if dte <= min_dte_to_hold:
        return "TIME_EXIT_READY"
    return "HOLD"
