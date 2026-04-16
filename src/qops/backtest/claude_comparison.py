"""Research-only Claude context filters and baseline comparisons for backtests."""

from __future__ import annotations

import math

from qops.backtest.replay_context import ReplayContext

_ALLOWED_MODES: frozenset[str] = frozenset(
    {
        "baseline",
        "exclude_materially_changed",
        "exclude_weakened_or_worse",
        "claude_only",
    }
)


def filter_contexts_by_claude_context(
    contexts: list[ReplayContext],
    *,
    mode: str = "baseline",
) -> list[ReplayContext]:
    """
    Return a filtered list of contexts using Claude research context only.

    Modes:
    - baseline: return all contexts.
    - exclude_materially_changed: drop contexts with Claude session MATERIALLY_CHANGED.
    - exclude_weakened_or_worse: drop contexts with Claude session WEAKENED or MATERIALLY_CHANGED.
    - claude_only: keep only contexts that carry Claude context.
    """
    if mode not in _ALLOWED_MODES:
        raise ValueError(
            f"invalid Claude filter mode: {mode!r}; allowed: {sorted(_ALLOWED_MODES)}"
        )

    if mode == "baseline":
        return list(contexts)

    filtered: list[ReplayContext] = []
    for ctx in contexts:
        cc = ctx.claude_context
        if mode == "exclude_materially_changed":
            if cc is not None and cc.session_reliability_state == "MATERIALLY_CHANGED":
                continue
            filtered.append(ctx)
            continue
        if mode == "exclude_weakened_or_worse":
            if cc is not None and cc.session_reliability_state in {
                "WEAKENED",
                "MATERIALLY_CHANGED",
            }:
                continue
            filtered.append(ctx)
            continue
        # claude_only
        if cc is not None:
            filtered.append(ctx)
    return filtered


def _delta(base: float, candidate: float) -> float:
    if math.isfinite(base) and math.isfinite(candidate):
        return candidate - base
    if base == candidate:
        return 0.0
    if not math.isfinite(base) and math.isfinite(candidate):
        return -math.inf if base > 0 else math.inf
    if math.isfinite(base) and not math.isfinite(candidate):
        return math.inf if candidate > 0 else -math.inf
    return 0.0


def run_claude_context_comparison(contexts: list[ReplayContext]) -> dict:
    """
    Run research-only comparison across:
    - baseline
    - exclude_materially_changed
    - exclude_weakened_or_worse
    - claude_only

    Returns per-mode ``run_iterative_backtest`` results and deltas vs baseline.
    """
    from qops.backtest.runner import run_iterative_backtest

    variant_order = (
        "baseline",
        "exclude_materially_changed",
        "exclude_weakened_or_worse",
        "claude_only",
    )
    variant_results: dict[str, dict] = {}
    for mode in variant_order:
        variant_contexts = filter_contexts_by_claude_context(contexts, mode=mode)
        variant_results[mode] = run_iterative_backtest(variant_contexts)

    baseline_summary = variant_results["baseline"]["summary"]
    deltas: dict[str, dict[str, float | int]] = {}
    for mode in variant_order[1:]:
        variant_summary = variant_results[mode]["summary"]
        deltas[mode] = {
            "trades_removed": baseline_summary.total_trades - variant_summary.total_trades,
            "net_pnl_change": _delta(baseline_summary.net_pnl, variant_summary.net_pnl),
            "profit_factor_change": _delta(
                baseline_summary.profit_factor, variant_summary.profit_factor
            ),
            "sharpe_change": _delta(baseline_summary.sharpe, variant_summary.sharpe),
        }

    return {
        "baseline": variant_results["baseline"],
        "exclude_materially_changed": variant_results["exclude_materially_changed"],
        "exclude_weakened_or_worse": variant_results["exclude_weakened_or_worse"],
        "claude_only": variant_results["claude_only"],
        "delta_vs_baseline": deltas,
    }
