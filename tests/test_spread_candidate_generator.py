"""STRUCT-C2: spread candidate generation from staged quotes."""

from __future__ import annotations

from qops.backtest.alpaca_greeks_layer import AlpacaGreeksCandidateRow
from qops.schemas.playbook import AllowedPlaybook
from qops.strategy.spread_candidate_generator import (
    StagedGreeksQuoteRow,
    generate_spread_candidates,
    summarize_spread_generation,
)


def _quote_row(
    *,
    option_symbol: str,
    strike: float,
    option_type: str,
    bid: float,
    ask: float,
    pmp: float | None = None,
) -> StagedGreeksQuoteRow:
    base = AlpacaGreeksCandidateRow(
        underlying_symbol="SPY",
        trade_date="2026-06-13",
        current_price=425.0,
        option_symbol=option_symbol,
        expiration="2026-06-20",
        strike=strike,
        option_type=option_type,
        bid=bid,
        ask=ask,
        mid=(bid + ask) / 2.0,
        latest_trade=None,
        delta=0.4,
        gamma=0.02,
        theta=-0.05,
        vega=0.1,
        rho=0.01,
        implied_volatility=0.2,
        greeks_source="alpaca_snapshot",
        greeks_status="AVAILABLE",
        greeks_confidence="high",
        volatility_is_proxy=False,
        provenance="test",
        blueprint_provenance="test",
        source_profile="test",
        has_spy_context=True,
    )
    return StagedGreeksQuoteRow(quote=base, probability_of_profit=pmp)


def test_bull_call_spread_from_quotes() -> None:
    rows = [
        _quote_row(option_symbol="C420", strike=420.0, option_type="call", bid=1.45, ask=1.50),
        _quote_row(option_symbol="C425", strike=425.0, option_type="call", bid=0.45, ask=0.50, pmp=0.40),
    ]
    candidates = generate_spread_candidates(rows, structures=[AllowedPlaybook.BULL_CALL_SPREAD.value])
    assert len(candidates) == 1
    c = candidates[0]
    assert c.structure_type == AllowedPlaybook.BULL_CALL_SPREAD.value
    assert c.spread_width == 5.0
    assert c.net_debit_or_credit == 1.50 - 0.45
    assert c.reference_strike == 420.0
    assert c.math.passes_spread_math_gate is True
    assert c.candidate_pass is True


def test_missing_pmp_not_pass() -> None:
    rows = [
        _quote_row(option_symbol="C420", strike=420.0, option_type="call", bid=4.5, ask=4.6),
        _quote_row(option_symbol="C425", strike=425.0, option_type="call", bid=1.4, ask=1.5),
    ]
    candidates = generate_spread_candidates(rows, structures=[AllowedPlaybook.BULL_CALL_SPREAD.value])
    assert len(candidates) == 1
    assert candidates[0].math.probability_status == "INCOMPLETE"
    assert candidates[0].candidate_pass is False


def test_empty_input_summary() -> None:
    summary = summarize_spread_generation(0, [])
    assert summary["spread_candidates_generated"] == 0
