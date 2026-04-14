"""Backtest summary, validation, and log row contracts plus first-pass gate logic."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True, slots=True)
class BacktestSummary:
    """Aggregate metrics from a backtest run."""

    total_trades: int
    net_pnl: float
    win_rate: float
    loss_rate: float
    avg_trade: float
    profit_factor: float
    sharpe: float
    max_drawdown: float | None
    stop_loss_rate: float | None
    stop_hit_rate: float | None
    avg_rr: float
    avg_pmp: float
    avg_dte: float
    avg_debit_size: float | None


class ValidationStatus(str, Enum):
    """Typed domain for backtest gate outcomes."""

    PASS = "PASS"
    WATCH = "WATCH"
    FAIL = "FAIL"


@dataclass(frozen=True, slots=True)
class BacktestValidationResult:
    """Paper-eligibility gate outcome for a backtest summary."""

    status: ValidationStatus
    reasons: list[str]
    eligible_for_paper: bool

    def __post_init__(self) -> None:
        if not isinstance(self.status, ValidationStatus):
            raise TypeError(
                f"status must be ValidationStatus, got {type(self.status).__name__}",
            )


@dataclass(frozen=True, slots=True)
class BacktestTradeLogRow:
    """Single trade row for backtest exports."""

    symbol: str
    playbook: str
    entry_date: str
    exit_date: str
    expiry: str
    regime_label: str
    confidence: int
    iv_state: str
    skew_state: str
    wall_state: str
    environment_label: str
    pmp: float
    rr_actual: float
    debit_or_credit: float
    max_profit: float
    max_loss: float
    exit_reason: str
    pnl: float
    candidate_alternatives: list[str] | None

    overlay_surface_state: str | None = None
    overlay_market_state: str | None = None
    overlay_term_structure_state: str | None = None
    overlay_caution_flag: bool | None = None
    overlay_downgrade_flag: bool | None = None


def evaluate_backtest_gate(
    summary: BacktestSummary,
    *,
    research_mode_exception: bool = False,
) -> BacktestValidationResult:
    """
    Apply deterministic first-pass rules for paper eligibility.

    FAIL if core minimums are not met and no research exception applies.
    WATCH when evidence is incomplete or borderline.
    PASS when required minimums are clearly met.
    """
    reasons: list[str] = []

    pf = summary.profit_factor
    sh = summary.sharpe
    trades = summary.total_trades

    pf_finite = math.isfinite(pf)
    sh_finite = math.isfinite(sh)

    fail_pf = pf_finite and pf <= 1.15
    fail_sh = sh_finite and sh <= 0.30
    fail_trades = trades < 30

    if (fail_pf or fail_sh or fail_trades) and not research_mode_exception:
        if fail_pf:
            reasons.append("profit_factor_at_or_below_minimum")
        if fail_sh:
            reasons.append("sharpe_at_or_below_minimum")
        if fail_trades:
            reasons.append("insufficient_trade_count")
        return BacktestValidationResult(
            status=ValidationStatus.FAIL,
            reasons=reasons,
            eligible_for_paper=False,
        )

    if not pf_finite or not sh_finite:
        reasons.append("non_finite_core_metric")
        return BacktestValidationResult(
            status=ValidationStatus.WATCH,
            reasons=reasons,
            eligible_for_paper=False,
        )

    pass_pf = pf > 1.15
    pass_sh = sh > 0.30
    pass_trades = trades >= 30

    borderline_pf = 1.15 < pf <= 1.25
    borderline_sh = 0.30 < sh <= 0.45
    borderline_trades = 30 <= trades < 45
    incomplete = summary.max_drawdown is None

    if pass_pf and pass_sh and pass_trades and not borderline_pf and not borderline_sh and not incomplete:
        reasons.append("meets_minimum_thresholds")
        return BacktestValidationResult(
            status=ValidationStatus.PASS,
            reasons=reasons,
            eligible_for_paper=True,
        )

    if borderline_pf:
        reasons.append("borderline_profit_factor")
    if borderline_sh:
        reasons.append("borderline_sharpe")
    if borderline_trades:
        reasons.append("borderline_trade_count")
    if incomplete:
        reasons.append("incomplete_evidence")
    if not reasons:
        reasons.append("unmatched_validation_path")
    return BacktestValidationResult(
        status=ValidationStatus.WATCH,
        reasons=reasons,
        eligible_for_paper=False,
    )
