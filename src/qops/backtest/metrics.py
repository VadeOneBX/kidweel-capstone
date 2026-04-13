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


def stop_loss_rate(exit_reasons: list[str]) -> float:
    """Return fraction of exits that are STOP."""
    if not exit_reasons:
        return 0.0
    stops = sum(1 for reason in exit_reasons if reason == "STOP")
    return stops / len(exit_reasons)


def stop_hit_rate(exit_reasons: list[str]) -> float:
    """
    Alias-like helper for STOP frequency, kept explicit for reporting.

    Matches stop_loss_rate for deterministic STOP-only counting.
    """
    return stop_loss_rate(exit_reasons)


def max_drawdown_from_pnls(pnls: list[float]) -> float:
    """
    Compute simple peak-to-trough drawdown from cumulative PnL path.

    Returns the most negative drawdown in PnL units (<= 0). Returns 0.0 for empty input.
    """
    if not pnls:
        return 0.0
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in pnls:
        cumulative += pnl
        peak = max(peak, cumulative)
        dd = cumulative - peak
        max_dd = min(max_dd, dd)
    return max_dd


def sharpe_from_pnls(pnls: list[float]) -> float:
    """
    Compute a simple per-trade Sharpe-like ratio (mean / sample std).

    Return 0.0 when undefined (empty, single trade, or zero variance).
    """
    if len(pnls) < 2:
        return 0.0
    mean = sum(pnls) / len(pnls)
    variance = sum((x - mean) ** 2 for x in pnls) / (len(pnls) - 1)
    if variance <= 0.0 or not math.isfinite(variance):
        return 0.0
    std = math.sqrt(variance)
    if std <= 0.0 or not math.isfinite(std):
        return 0.0
    ratio = mean / std
    return ratio if math.isfinite(ratio) else 0.0
