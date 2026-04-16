"""Builders and validators for backtest trade log rows."""

from __future__ import annotations

import math

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from qops.backtest.replay_context import ReplayContext
from qops.schemas.backtest import BacktestTradeLogRow


def build_trade_log_row(
    *,
    symbol: str,
    playbook: str,
    entry_date: str,
    exit_date: str,
    expiry: str,
    regime_label: str,
    confidence: int,
    iv_state: str,
    skew_state: str,
    wall_state: str,
    environment_label: str,
    pmp: float,
    rr_actual: float,
    debit_or_credit: float,
    max_profit: float,
    max_loss: float,
    exit_reason: str,
    pnl: float,
    candidate_alternatives: list[str] | None = None,
    overlay_surface_state: str | None = None,
    overlay_market_state: str | None = None,
    overlay_term_structure_state: str | None = None,
    overlay_caution_flag: bool | None = None,
    overlay_downgrade_flag: bool | None = None,
    claude_source_type: str | None = None,
    claude_file_regime_label: str | None = None,
    claude_file_confidence: int | None = None,
    claude_session_reliability_state: str | None = None,
    claude_context_note: str | None = None,
    claude_confidence_adjustment_note: str | None = None,
    claude_classification_note: str | None = None,
) -> BacktestTradeLogRow:
    """Build a validated BacktestTradeLogRow."""
    if not symbol.strip():
        raise ValueError("symbol must be non-empty")
    if not playbook.strip():
        raise ValueError("playbook must be non-empty")
    if not entry_date.strip() or not exit_date.strip() or not expiry.strip():
        raise ValueError("entry_date, exit_date, and expiry must be non-empty")
    if isinstance(confidence, bool) or not isinstance(confidence, int):
        raise ValueError("confidence must be an integer on the 0–10 scale")
    if not (0 <= confidence <= 10):
        raise ValueError("confidence must be between 0 and 10 inclusive")
    if debit_or_credit <= 0.0 or not math.isfinite(debit_or_credit):
        raise ValueError("debit_or_credit must be finite and > 0")
    if max_profit <= 0.0 or not math.isfinite(max_profit):
        raise ValueError("max_profit must be finite and > 0")
    if max_loss <= 0.0 or not math.isfinite(max_loss):
        raise ValueError("max_loss must be finite and > 0")
    if not exit_reason.strip():
        raise ValueError("exit_reason must be non-empty")
    if not math.isfinite(pmp):
        raise ValueError("pmp must be finite")
    if not math.isfinite(rr_actual):
        raise ValueError("rr_actual must be finite")
    if not math.isfinite(pnl):
        raise ValueError("pnl must be finite")

    return BacktestTradeLogRow(
        symbol=symbol,
        playbook=playbook,
        entry_date=entry_date,
        exit_date=exit_date,
        expiry=expiry,
        regime_label=regime_label,
        confidence=confidence,
        iv_state=iv_state,
        skew_state=skew_state,
        wall_state=wall_state,
        environment_label=environment_label,
        pmp=pmp,
        rr_actual=rr_actual,
        debit_or_credit=debit_or_credit,
        max_profit=max_profit,
        max_loss=max_loss,
        exit_reason=exit_reason,
        pnl=pnl,
        candidate_alternatives=candidate_alternatives,
        overlay_surface_state=overlay_surface_state,
        overlay_market_state=overlay_market_state,
        overlay_term_structure_state=overlay_term_structure_state,
        overlay_caution_flag=overlay_caution_flag,
        overlay_downgrade_flag=overlay_downgrade_flag,
        claude_source_type=claude_source_type,
        claude_file_regime_label=claude_file_regime_label,
        claude_file_confidence=claude_file_confidence,
        claude_session_reliability_state=claude_session_reliability_state,
        claude_context_note=claude_context_note,
        claude_confidence_adjustment_note=claude_confidence_adjustment_note,
        claude_classification_note=claude_classification_note,
    )


def build_trade_log_row_from_context(ctx: ReplayContext) -> BacktestTradeLogRow:
    """Build a validated BacktestTradeLogRow from ReplayContext."""
    structure = ctx.structure
    evaluation = ctx.evaluation
    overlay = ctx.overlay
    overlay_surface: str | None = None
    overlay_market: str | None = None
    overlay_term: str | None = None
    overlay_caution: bool | None = None
    overlay_downgrade: bool | None = None
    if overlay is not None:
        overlay_surface = overlay.surface_state
        overlay_market = overlay.market_state
        overlay_term = overlay.term_structure_state
        overlay_caution = overlay.caution_flag
        overlay_downgrade = overlay.downgrade_flag

    cc = ctx.claude_context
    claude_source: str | None = None
    claude_regime: str | None = None
    claude_fconf: int | None = None
    claude_sess: str | None = None
    claude_ctx_note: str | None = None
    claude_conf_adj: str | None = None
    claude_class_note: str | None = None
    if cc is not None:
        claude_source = cc.source_type
        claude_regime = cc.file_regime_label
        claude_fconf = cc.file_confidence
        claude_sess = cc.session_reliability_state
        claude_ctx_note = cc.context_note
        claude_conf_adj = cc.confidence_adjustment_note
        claude_class_note = cc.classification_note

    return build_trade_log_row(
        symbol=ctx.symbol,
        playbook=ctx.playbook,
        entry_date=ctx.entry_date,
        exit_date=ctx.exit_date,
        expiry=structure.expiry,
        regime_label=structure.regime_label.value,
        confidence=structure.confidence,
        iv_state=structure.iv_state.value,
        skew_state=structure.skew_state.value,
        wall_state=structure.wall_state.value,
        environment_label=ctx.environment_label,
        pmp=evaluation.pmp,
        rr_actual=structure.rr_actual,
        debit_or_credit=structure.debit_or_credit,
        max_profit=structure.max_profit,
        max_loss=structure.max_loss,
        exit_reason=ctx.exit_reason,
        pnl=ctx.realized_pnl,
        candidate_alternatives=ctx.candidate_alternatives,
        overlay_surface_state=overlay_surface,
        overlay_market_state=overlay_market,
        overlay_term_structure_state=overlay_term,
        overlay_caution_flag=overlay_caution,
        overlay_downgrade_flag=overlay_downgrade,
        claude_source_type=claude_source,
        claude_file_regime_label=claude_regime,
        claude_file_confidence=claude_fconf,
        claude_session_reliability_state=claude_sess,
        claude_context_note=claude_ctx_note,
        claude_confidence_adjustment_note=claude_conf_adj,
        claude_classification_note=claude_class_note,
    )
