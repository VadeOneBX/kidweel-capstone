"""Reverse-VRP dealer direction scoring (C2C enablement)."""

from __future__ import annotations

from qops.pipeline.alpaca_hydration_loop import _score_expression
from qops.strategy.dealer_expression_tier import (
    DIRECTION_STATUS_SOURCE_DERIVED,
    DIRECTION_STATUS_SOURCE_MISSING,
    REVERSE_VRP_DIRECTION_SOURCE,
    resolve_dealer_direction_score,
    reverse_vrp_direction_row_from_mapping,
    reverse_vrp_direction_score,
)
from qops.strategy.spread_candidate_generator import GeneratedSpreadCandidate, SpreadMathEvaluation


def _reverse_vrp_candidate_row() -> dict[str, object]:
    return {
        "symbol": "ONDS",
        "trade_date": "2026-06-18",
        "source_profile": "reverse_vrp",
        "current_price": 3.0,
        "call_wall": 3.5,
        "put_wall": 2.5,
        "hedge_wall": 3.1,
        "skew": 0.0,
        "one_month_iv": 0.55,
        "one_month_rv": 0.60,
        "vrp": -0.05,
        "iv_rank": 25.0,
    }


def _bull_call_expr(*, short_strike_offset: float = 0.5) -> GeneratedSpreadCandidate:
    ref = 3.0
    width = short_strike_offset
    math = SpreadMathEvaluation(
        structure_type="BULL_CALL_SPREAD",
        spread_width=width,
        net_debit_or_credit=0.2,
        max_profit=width - 0.2,
        max_loss=0.2,
        reward_risk=1.5,
        break_even=ref + 0.2,
        capital_at_risk=0.2,
        probability_of_profit=0.4,
        expected_value=0.05,
        rr_required=1.0,
        pass_reward_risk=True,
        pass_probability=True,
        pass_ev=True,
        ev_status="PASS",
        probability_status="PASS",
        passes_spread_math_gate=True,
        failure_reasons=(),
    )
    return GeneratedSpreadCandidate(
        structure_type="BULL_CALL_SPREAD",
        underlying_symbol="ONDS",
        trade_date="2026-06-18",
        expiration="2026-06-25",
        long_option_symbol="ONDS250625C00003000",
        short_option_symbol="ONDS250625C00003500",
        spread_width=width,
        net_debit_or_credit=0.2,
        reference_strike=ref,
        probability_of_profit=0.4,
        math=math,
        candidate_pass=True,
        builder_succeeded=True,
        failure_reasons=(),
        provenance="test",
        greeks_provenance="test",
        long_greeks_source="alpaca_snapshot",
        long_greeks_confidence="high",
        short_greeks_source="alpaca_snapshot",
        short_greeks_confidence="high",
        pmp_for_gate=0.4,
        pmp_source="proxy",
        pmp_method="delta",
        pmp_proxy_status="PMP_PROXY_AVAILABLE",
        pmp_confidence="LOW",
        pmp_inputs_used=("delta",),
    )


def test_reverse_vrp_direction_score_uses_iv_rv_wall_skew() -> None:
    row = reverse_vrp_direction_row_from_mapping(_reverse_vrp_candidate_row())
    score, reasons = reverse_vrp_direction_score(
        row,
        structure="BULL_CALL_SPREAD",
        short_strike=3.5,
    )
    assert score >= 2
    assert "cheap_iv_vrp_negative" in reasons
    assert "call_wall_above_spot" in reasons


def test_reverse_vrp_direction_score_does_not_require_gamma_ratio() -> None:
    candidate = _reverse_vrp_candidate_row()
    assert "gamma_ratio" not in candidate
    scored = _score_expression(_bull_call_expr(), candidate_row=candidate)
    assert int(scored["dealer_direction_score"]) > 0


def test_reverse_vrp_direction_score_marks_source_derived() -> None:
    candidate = _reverse_vrp_candidate_row()
    scored = _score_expression(_bull_call_expr(), candidate_row=candidate)
    assert scored["dealer_direction_score_source"] == REVERSE_VRP_DIRECTION_SOURCE
    assert scored["dealer_direction_score_status"] == DIRECTION_STATUS_SOURCE_DERIVED


def test_reverse_vrp_missing_direction_fields_visible_not_silent() -> None:
    candidate = {"source_profile": "reverse_vrp", "symbol": "X"}
    resolution = resolve_dealer_direction_score(
        source_profile="reverse_vrp",
        gamma_ratio=None,
        candidate_row=candidate,
        structure="BULL_CALL_SPREAD",
        short_strike=1.0,
    )
    assert resolution.score == 0
    assert resolution.status == DIRECTION_STATUS_SOURCE_MISSING
    assert "missing_reverse_vrp_direction_fields" in resolution.reason
