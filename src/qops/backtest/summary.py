"""Backtest summary construction and canonical gate validation wrappers."""

from __future__ import annotations

from qops.backtest.metrics import average_trade, loss_rate, profit_factor, total_pnl, win_rate

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from qops.schemas.backtest import (
    BacktestSummary,
    BacktestValidationResult,
    evaluate_backtest_gate,
)


def build_backtest_summary(
    pnls: list[float],
    avg_rr: float,
    avg_pmp: float,
    avg_dte: float,
    avg_debit_size: float | None,
    max_drawdown: float | None = None,
    stop_loss_rate: float | None = None,
    stop_hit_rate: float | None = None,
    sharpe: float = 0.0,
) -> BacktestSummary:
    """Build a BacktestSummary from deterministic inputs and simple metrics."""
    return BacktestSummary(
        total_trades=len(pnls),
        net_pnl=total_pnl(pnls),
        win_rate=win_rate(pnls),
        loss_rate=loss_rate(pnls),
        avg_trade=average_trade(pnls),
        profit_factor=profit_factor(pnls),
        sharpe=sharpe,
        max_drawdown=max_drawdown,
        stop_loss_rate=stop_loss_rate,
        stop_hit_rate=stop_hit_rate,
        avg_rr=avg_rr,
        avg_pmp=avg_pmp,
        avg_dte=avg_dte,
        avg_debit_size=avg_debit_size,
    )


def validate_backtest_summary(
    summary: BacktestSummary,
    research_mode_exception: bool = False,
) -> BacktestValidationResult:
    """Validate summary using the canonical PASS / WATCH / FAIL policy path."""
    return evaluate_backtest_gate(
        summary=summary,
        research_mode_exception=research_mode_exception,
    )


def build_segment_metrics(
    pnls: list[float],
    sharpe: float,
    stop_loss_rate: float | None = None,
) -> dict:
    """
    Return a compact metrics dictionary for grouped reporting.

    Keys are stable: trades, net_pnl, profit_factor, sharpe, stop_loss_rate.
    """
    return {
        "trades": len(pnls),
        "net_pnl": total_pnl(pnls),
        "profit_factor": profit_factor(pnls),
        "sharpe": sharpe,
        "stop_loss_rate": stop_loss_rate if stop_loss_rate is not None else 0.0,
    }
