"""Backtest metrics, summary helpers, replay context, and iterative runner."""

from __future__ import annotations

from qops.backtest.metrics import (
    average_trade,
    loss_rate,
    max_drawdown_from_pnls,
    profit_factor,
    sharpe_from_pnls,
    stop_hit_rate,
    stop_loss_rate,
    total_pnl,
    win_rate,
)
from qops.backtest.overlay_filter import (
    filter_contexts_by_overlay,
    run_overlay_comparison,
    run_overlay_variant_comparisons,
)
from qops.backtest.replay_context import ReplayContext, validate_replay_context
from qops.backtest.claude_context import ClaudeCandidateContext
from qops.backtest.claude_comparison import (
    filter_contexts_by_claude_context,
    run_claude_context_comparison,
)
from qops.backtest.runner import format_evidence_block, format_metric_value, run_iterative_backtest
from qops.backtest.alpaca_replay_inputs import (
    AlpacaReplayInputPlanRow,
    build_availability_plan,
    load_replay_candidates,
    load_replay_candidates_from_csv,
    plan_to_dataframe,
    summarize_availability_plan,
)
from qops.backtest.spotgamma_replay_builder import (
    ReplayCandidateRow,
    build_replay_candidates,
    candidates_to_dataframe,
    load_contexts_from_csv,
    summarize_replay_candidates,
)
from qops.backtest.summary import (
    build_backtest_summary,
    build_claude_context_metrics,
    build_overlay_metrics,
    build_segment_metrics,
    validate_backtest_summary,
)
from qops.backtest.trade_log import build_trade_log_row, build_trade_log_row_from_context

__all__ = [
    "AlpacaReplayInputPlanRow",
    "ClaudeCandidateContext",
    "ReplayContext",
    "ReplayCandidateRow",
    "average_trade",
    "build_availability_plan",
    "build_backtest_summary",
    "build_claude_context_metrics",
    "build_overlay_metrics",
    "build_replay_candidates",
    "build_segment_metrics",
    "build_trade_log_row",
    "build_trade_log_row_from_context",
    "candidates_to_dataframe",
    "format_evidence_block",
    "format_metric_value",
    "filter_contexts_by_claude_context",
    "filter_contexts_by_overlay",
    "load_replay_candidates",
    "load_replay_candidates_from_csv",
    "load_contexts_from_csv",
    "loss_rate",
    "max_drawdown_from_pnls",
    "plan_to_dataframe",
    "profit_factor",
    "run_iterative_backtest",
    "run_claude_context_comparison",
    "run_overlay_comparison",
    "run_overlay_variant_comparisons",
    "sharpe_from_pnls",
    "stop_hit_rate",
    "stop_loss_rate",
    "summarize_availability_plan",
    "summarize_replay_candidates",
    "total_pnl",
    "validate_backtest_summary",
    "validate_replay_context",
    "win_rate",
]
