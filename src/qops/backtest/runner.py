"""Deterministic iterative backtest aggregation and evidence formatting."""

from __future__ import annotations

import math

from qops.backtest.metrics import (
    max_drawdown_from_pnls,
    sharpe_from_pnls,
    stop_hit_rate,
    stop_loss_rate,
)
from qops.backtest.replay_context import ReplayContext, validate_replay_context
from qops.backtest.summary import (
    build_backtest_summary,
    build_overlay_metrics,
    build_segment_metrics,
    validate_backtest_summary,
)
from qops.backtest.trade_log import build_trade_log_row_from_context

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from qops.schemas.backtest import BacktestSummary, BacktestTradeLogRow, BacktestValidationResult


def _fmt_decimal2(value: float) -> str:
    """Format finite floats with two decimal places; non-finite pass through as str."""
    if not math.isfinite(value):
        return str(value)
    return f"{value:.2f}"


def format_metric_value(value: float, *, signed: bool = False) -> str:
    """
    Return a stable display string for artifact output.

    Rules:
    - inf -> "INF" or "+INF" if signed=True
    - -inf -> "-INF"
    - nan -> "N/A"
    - finite floats -> format to 2 decimals, with optional sign
    """
    if math.isnan(value):
        return "N/A"
    if value == math.inf:
        return "+INF" if signed else "INF"
    if value == -math.inf:
        return "-INF"
    return f"{value:+.2f}" if signed else f"{value:.2f}"


def _fmt_pct(value: float) -> str:
    """Format a fractional rate (0–1) as a percentage for evidence display."""
    if not math.isfinite(value):
        return str(value)
    return f"{100.0 * value:.1f}%"


def _fmt_pf(value: float) -> str:
    return format_metric_value(value)


def _fmt_signed_decimal2(value: float) -> str:
    """Format signed finite float with explicit sign and two decimals."""
    return format_metric_value(value, signed=True)


def format_evidence_block(
    summary: BacktestSummary,
    validation: BacktestValidationResult,
    playbook_metrics: dict,
    environment_metrics: dict,
    overlay_metrics: dict | None = None,
    overlay_comparison: dict | None = None,
) -> str:
    """Return a human-readable evidence block for reporting."""
    stop_share = summary.stop_loss_rate if summary.stop_loss_rate is not None else 0.0
    lines: list[str] = [
        "Backtest Summary",
        "---------------",
        f"Trades: {summary.total_trades}",
        f"Net PnL: {_fmt_decimal2(summary.net_pnl)}",
        f"Profit Factor: {_fmt_pf(summary.profit_factor)}",
        f"Sharpe: {_fmt_decimal2(summary.sharpe)}",
    ]
    if summary.max_drawdown is None:
        lines.append("Max Drawdown (PnL): n/a")
    else:
        lines.append(f"Max Drawdown (PnL): {_fmt_decimal2(summary.max_drawdown)}")
    lines.extend(
        [
            f"Win Rate: {_fmt_pct(summary.win_rate)}",
            f"Stop Rate (STOP share): {_fmt_pct(stop_share)}",
            "",
            f"Avg RR: {_fmt_decimal2(summary.avg_rr)}",
            f"Avg PMP: {_fmt_pct(summary.avg_pmp)}",
            "",
            f"Validation: {validation.status.value}",
            "",
            "Playbook Performance",
            "--------------------",
        ]
    )
    for playbook in sorted(playbook_metrics.keys()):
        seg = playbook_metrics[playbook]
        slr = seg.get("stop_loss_rate", 0.0)
        lines.extend(
            [
                f"{playbook}:",
                f"  Trades: {seg['trades']}",
                f"  Net PnL: {_fmt_decimal2(seg['net_pnl'])}",
                f"  PF: {_fmt_pf(seg['profit_factor'])}",
                f"  Sharpe: {_fmt_decimal2(seg['sharpe'])}",
                f"  Stop Loss Rate: {_fmt_pct(float(slr))}",
                "",
            ]
        )
    lines.extend(
        [
            "Environment Performance",
            "-----------------------",
        ]
    )
    for env_label in sorted(environment_metrics.keys()):
        seg = environment_metrics[env_label]
        slr = seg.get("stop_loss_rate", 0.0)
        lines.extend(
            [
                f"{env_label}:",
                f"  Trades: {seg['trades']}",
                f"  Net PnL: {_fmt_decimal2(seg['net_pnl'])}",
                f"  PF: {_fmt_pf(seg['profit_factor'])}",
                f"  Sharpe: {_fmt_decimal2(seg['sharpe'])}",
                f"  Stop Loss Rate: {_fmt_pct(float(slr))}",
                "",
            ]
        )
    if overlay_metrics:
        lines.extend(
            [
                "",
                "Overlay Performance",
                "-------------------",
            ]
        )
        for key in sorted(overlay_metrics.keys()):
            seg = overlay_metrics[key]
            slr = seg.get("stop_loss_rate", 0.0)
            lines.extend(
                [
                    f"{key}:",
                    f"  Trades: {seg['trades']}",
                    f"  Net PnL: {_fmt_decimal2(seg['net_pnl'])}",
                    f"  PF: {_fmt_pf(seg['profit_factor'])}",
                    f"  Sharpe: {_fmt_decimal2(seg['sharpe'])}",
                    f"  Stop Loss Rate: {_fmt_pct(float(slr))}",
                    "",
                ]
            )
    if overlay_comparison:
        baseline = overlay_comparison.get("baseline")
        filtered = overlay_comparison.get("exclude_downgraded")
        delta = overlay_comparison.get("delta")
        if delta is None:
            delta = overlay_comparison.get("delta_vs_baseline", {}).get("exclude_downgraded")
        if baseline is not None and filtered is not None and delta is not None:
            bsum = baseline.get("summary")
            fsum = filtered.get("summary")
            if bsum is not None and fsum is not None:
                lines.extend(
                    [
                        "",
                        "Overlay Comparison",
                        "------------------",
                        "Baseline:",
                        f"  Trades: {bsum.total_trades}",
                        f"  PF: {_fmt_pf(bsum.profit_factor)}",
                        f"  Sharpe: {_fmt_decimal2(bsum.sharpe)}",
                        "Exclude Downgraded:",
                        f"  Trades: {fsum.total_trades}",
                        f"  PF: {_fmt_pf(fsum.profit_factor)}",
                        f"  Sharpe: {_fmt_decimal2(fsum.sharpe)}",
                        "Delta:",
                        f"  Trades Removed: {delta.get('trades_removed', 0)}",
                        f"  Net PnL Change: {_fmt_signed_decimal2(float(delta.get('net_pnl_change', 0.0)))}",
                        f"  PF Change: {_fmt_signed_decimal2(float(delta.get('profit_factor_change', 0.0)))}",
                        f"  Sharpe Change: {_fmt_signed_decimal2(float(delta.get('sharpe_change', 0.0)))}",
                    ]
                )
    return "\n".join(lines).rstrip() + "\n"


def _bucket_segment_metrics(
    bucket_pnls: dict[str, list[float]],
    bucket_exits: dict[str, list[str]],
) -> dict[str, dict]:
    metrics: dict[str, dict] = {}
    for key in sorted(bucket_pnls.keys()):
        pnls = bucket_pnls[key]
        exits = bucket_exits.get(key, [])
        slr = stop_loss_rate(exits) if exits else 0.0
        sh = sharpe_from_pnls(pnls)
        metrics[key] = build_segment_metrics(pnls, sh, slr)
    return metrics


def run_iterative_backtest(
    contexts: list[ReplayContext],
    *,
    research_mode_exception: bool = False,
) -> dict:
    """
    Run deterministic backtest aggregation over replay contexts.

    Returns a dictionary containing summary, validation, trade_log, playbook_metrics,
    environment_metrics, overlay_metrics, and evidence_block.
    """
    trade_log: list[BacktestTradeLogRow] = []
    pnls: list[float] = []
    exit_reasons: list[str] = []

    playbook_pnls: dict[str, list[float]] = {}
    playbook_exits: dict[str, list[str]] = {}

    env_pnls: dict[str, list[float]] = {}
    env_exits: dict[str, list[str]] = {}

    for ctx in contexts:
        validate_replay_context(ctx)
        trade_log.append(build_trade_log_row_from_context(ctx))
        pnls.append(ctx.realized_pnl)
        exit_reasons.append(ctx.exit_reason)

        playbook_pnls.setdefault(ctx.playbook, []).append(ctx.realized_pnl)
        playbook_exits.setdefault(ctx.playbook, []).append(ctx.exit_reason)

        env_pnls.setdefault(ctx.environment_label, []).append(ctx.realized_pnl)
        env_exits.setdefault(ctx.environment_label, []).append(ctx.exit_reason)

    n = len(contexts)
    avg_rr = sum(c.structure.rr_actual for c in contexts) / n if n else 0.0
    avg_pmp = sum(c.evaluation.pmp for c in contexts) / n if n else 0.0
    avg_dte = sum(c.dte_at_entry for c in contexts) / n if n else 0.0
    avg_debit = sum(c.structure.debit_or_credit for c in contexts) / n if n else None

    sharpe = sharpe_from_pnls(pnls)
    max_dd: float | None = max_drawdown_from_pnls(pnls) if n else None
    slr = stop_loss_rate(exit_reasons) if n else None
    shr = stop_hit_rate(exit_reasons) if n else None

    summary = build_backtest_summary(
        pnls=pnls,
        avg_rr=avg_rr,
        avg_pmp=avg_pmp,
        avg_dte=avg_dte,
        avg_debit_size=avg_debit,
        max_drawdown=max_dd,
        stop_loss_rate=slr,
        stop_hit_rate=shr,
        sharpe=sharpe,
    )
    validation = validate_backtest_summary(
        summary=summary,
        research_mode_exception=research_mode_exception,
    )

    playbook_metrics = _bucket_segment_metrics(playbook_pnls, playbook_exits)
    environment_metrics = _bucket_segment_metrics(env_pnls, env_exits)
    overlay_metrics = build_overlay_metrics(contexts)

    evidence_block = format_evidence_block(
        summary=summary,
        validation=validation,
        playbook_metrics=playbook_metrics,
        environment_metrics=environment_metrics,
        overlay_metrics=overlay_metrics,
    )

    return {
        "summary": summary,
        "validation": validation,
        "trade_log": trade_log,
        "playbook_metrics": playbook_metrics,
        "environment_metrics": environment_metrics,
        "overlay_metrics": overlay_metrics,
        "evidence_block": evidence_block,
    }
