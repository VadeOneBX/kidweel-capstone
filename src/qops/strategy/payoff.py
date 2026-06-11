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


def credit_spread_max_profit(net_credit: float) -> float:
    """Return max profit for a credit spread using max_profit = net_credit."""
    if net_credit <= 0:
        raise ValueError("net_credit must be > 0")
    return net_credit


def credit_spread_max_loss(width: float, net_credit: float) -> float:
    """Return max loss for a credit spread using max_loss = width - net_credit."""
    if width <= 0:
        raise ValueError("width must be > 0")
    if net_credit <= 0:
        raise ValueError("net_credit must be > 0")
    max_loss = width - net_credit
    if max_loss <= 0:
        raise ValueError("net_credit must be < width")
    return max_loss


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
