"""Backtest summary construction and canonical gate validation wrappers."""

from __future__ import annotations

from qops.backtest.metrics import (
    average_trade,
    loss_rate,
    profit_factor,
    sharpe_from_pnls,
    stop_loss_rate,
    total_pnl,
    win_rate,
)
from qops.backtest.replay_context import ReplayContext

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


def build_overlay_metrics(contexts: list[ReplayContext]) -> dict[str, dict]:
    """
    Return compact grouped overlay metrics (presence, caution, downgrade, surface state).

    Segments trades by overlay memo fields when present; omits empty buckets.
    Does not affect validation or approval — reporting only.
    """
    present_t: list[float] = []
    present_t_exits: list[str] = []
    present_f: list[float] = []
    present_f_exits: list[str] = []

    caution_t: list[float] = []
    caution_t_exits: list[str] = []
    caution_f: list[float] = []
    caution_f_exits: list[str] = []

    downgrade_t: list[float] = []
    downgrade_t_exits: list[str] = []
    downgrade_f: list[float] = []
    downgrade_f_exits: list[str] = []

    surface_pnls: dict[str, list[float]] = {}
    surface_exits: dict[str, list[str]] = {}

    for ctx in contexts:
        pnl = ctx.realized_pnl
        ex = ctx.exit_reason
        ov = ctx.overlay
        if ov is not None:
            present_t.append(pnl)
            present_t_exits.append(ex)
            if ov.caution_flag:
                caution_t.append(pnl)
                caution_t_exits.append(ex)
            else:
                caution_f.append(pnl)
                caution_f_exits.append(ex)
            if ov.downgrade_flag:
                downgrade_t.append(pnl)
                downgrade_t_exits.append(ex)
            else:
                downgrade_f.append(pnl)
                downgrade_f_exits.append(ex)
            sk = ov.surface_state
            surface_pnls.setdefault(sk, []).append(pnl)
            surface_exits.setdefault(sk, []).append(ex)
        else:
            present_f.append(pnl)
            present_f_exits.append(ex)

    out: dict[str, dict] = {}

    def _add(key: str, pnls: list[float], exits: list[str]) -> None:
        if not pnls:
            return
        slr = stop_loss_rate(exits) if exits else 0.0
        sh = sharpe_from_pnls(pnls)
        out[key] = build_segment_metrics(pnls, sh, slr)

    _add("overlay_present=True", present_t, present_t_exits)
    _add("overlay_present=False", present_f, present_f_exits)
    _add("overlay_caution_flag=True", caution_t, caution_t_exits)
    _add("overlay_caution_flag=False", caution_f, caution_f_exits)
    _add("overlay_downgrade_flag=True", downgrade_t, downgrade_t_exits)
    _add("overlay_downgrade_flag=False", downgrade_f, downgrade_f_exits)

    for surf in sorted(surface_pnls.keys()):
        pnls = surface_pnls[surf]
        exits = surface_exits.get(surf, [])
        _add(f"overlay_surface={surf}", pnls, exits)

    return out
