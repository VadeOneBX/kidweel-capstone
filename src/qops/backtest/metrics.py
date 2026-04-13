"""Deterministic summary metrics from simple PnL lists."""

from __future__ import annotations

import math


def total_pnl(pnls: list[float]) -> float:
    """Return total PnL."""
    return sum(pnls)


def win_rate(pnls: list[float]) -> float:
    """Return fraction of trades with pnl > 0."""
    if not pnls:
        return 0.0
    wins = sum(1 for pnl in pnls if pnl > 0.0)
    return wins / len(pnls)


def loss_rate(pnls: list[float]) -> float:
    """Return fraction of trades with pnl < 0."""
    if not pnls:
        return 0.0
    losses = sum(1 for pnl in pnls if pnl < 0.0)
    return losses / len(pnls)


def average_trade(pnls: list[float]) -> float:
    """Return average PnL per trade."""
    if not pnls:
        return 0.0
    return sum(pnls) / len(pnls)


def profit_factor(pnls: list[float]) -> float:
    """
    Return gross profit / gross loss.

    Returns 0.0 if there are no losses and no gains.
    Returns inf if there are gains and zero losses.
    """
    gross_profit = sum(pnl for pnl in pnls if pnl > 0.0)
    gross_loss = -sum(pnl for pnl in pnls if pnl < 0.0)
    if gross_loss == 0.0:
        if gross_profit == 0.0:
            return 0.0
        return math.inf
    return gross_profit / gross_loss
