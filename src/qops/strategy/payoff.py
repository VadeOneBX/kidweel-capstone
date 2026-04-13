"""Deterministic payoff math for debit spreads."""

from __future__ import annotations


def _validate_debit_spread_inputs(width: float, debit: float) -> None:
    if width <= 0:
        raise ValueError("width must be > 0")
    if debit <= 0:
        raise ValueError("debit must be > 0")
    if debit >= width:
        raise ValueError("debit must be < width")


def debit_spread_max_profit(width: float, debit: float) -> float:
    """Return max profit for a debit spread using max_profit = width - debit."""
    _validate_debit_spread_inputs(width, debit)
    return width - debit


def debit_spread_max_loss(debit: float) -> float:
    """Return max loss for a debit spread using max_loss = debit."""
    if debit <= 0:
        raise ValueError("debit must be > 0")
    return debit


def debit_spread_breakeven(long_strike: float, debit: float, bullish: bool) -> float:
    """
    Return expiration breakeven for bull call or bear put spreads.

    Bull call: long_strike + debit
    Bear put: long_strike - debit
    """
    if debit <= 0:
        raise ValueError("debit must be > 0")
    if bullish:
        return long_strike + debit
    return long_strike - debit
