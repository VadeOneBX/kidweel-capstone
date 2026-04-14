"""Research-only overlay filter/comparison helpers for backtest outputs."""

from __future__ import annotations

import math

from qops.backtest.replay_context import ReplayContext
from qops.backtest.runner import run_iterative_backtest

_ALLOWED_MODES: frozenset[str] = frozenset(
    {
        "baseline",
        "exclude_downgraded",
        "exclude_caution",
        "overlay_only",
        "determined",
    }
)


def filter_contexts_by_overlay(
    contexts: list[ReplayContext],
    *,
    mode: str = "baseline",
) -> list[ReplayContext]:
    """
    Return a deterministic research-view context list for overlay comparison.

    Modes:
    - baseline: return all contexts unchanged.
    - exclude_downgraded: drop contexts where overlay exists and downgrade_flag is True.
    - exclude_caution: drop contexts where overlay exists and caution_flag is True.
    - overlay_only: keep only contexts where overlay exists.
    - determined: keep only contexts where overlay exists and either caution_flag or downgrade_flag is True.
    """
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"invalid overlay filter mode: {mode!r}; allowed: {sorted(_ALLOWED_MODES)}")

    if mode == "baseline":
        return list(contexts)

    filtered: list[ReplayContext] = []
    for ctx in contexts:
        ov = ctx.overlay
        if mode == "exclude_downgraded":
            if ov is not None and ov.downgrade_flag:
                continue
            filtered.append(ctx)
            continue
        if mode == "exclude_caution":
            if ov is not None and ov.caution_flag:
                continue
            filtered.append(ctx)
            continue
        if mode == "overlay_only":
            if ov is not None:
                filtered.append(ctx)
            continue
        # determined is a pressure-test slice, not an operational filter.
        if ov is not None and (ov.downgrade_flag or ov.caution_flag):
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


def run_overlay_variant_comparisons(contexts: list[ReplayContext]) -> dict:
    """
    Run research-only comparisons across:
    - baseline
    - exclude_downgraded
    - exclude_caution
    - overlay_only
    - determined

    Returns a dictionary keyed by variant name plus deltas vs baseline.
    """
    variant_order = (
        "baseline",
        "exclude_downgraded",
        "exclude_caution",
        "overlay_only",
        "determined",
    )
    variant_results: dict[str, dict] = {}
    for mode in variant_order:
        variant_contexts = filter_contexts_by_overlay(contexts, mode=mode)
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
        "exclude_downgraded": variant_results["exclude_downgraded"],
        "exclude_caution": variant_results["exclude_caution"],
        "overlay_only": variant_results["overlay_only"],
        "determined": variant_results["determined"],
        "delta_vs_baseline": deltas,
    }


def run_overlay_comparison(contexts: list[ReplayContext]) -> dict:
    """
    Run baseline vs overlay-filtered research comparison using canonical backtest logic.

    Returns:
        {
            "baseline": <run_iterative_backtest result>,
            "exclude_downgraded": <run_iterative_backtest result>,
            "delta": {
                "trades_removed": int,
                "net_pnl_change": float,
                "profit_factor_change": float,
                "sharpe_change": float,
            },
        }
    """
    comparisons = run_overlay_variant_comparisons(contexts)
    return {
        "baseline": comparisons["baseline"],
        "exclude_downgraded": comparisons["exclude_downgraded"],
        "delta": comparisons["delta_vs_baseline"]["exclude_downgraded"],
    }
