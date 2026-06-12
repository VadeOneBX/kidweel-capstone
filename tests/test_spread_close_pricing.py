from __future__ import annotations

from unittest.mock import patch

import pytest

from qops.execution.paper_payload_candidate import PaperPayloadCandidate
from qops.execution.spread_close_pricing import (
    OptionLegQuote,
    calculate_spread_close_mid,
    fetch_alpaca_option_latest_quotes,
    leg_mid_from_bid_ask,
    price_spread_close,
    round_option_limit_price,
)
from qops.schemas.playbook import AllowedPlaybook


def _payload(**overrides: object) -> PaperPayloadCandidate:
    base = dict(
        payload_id="pay001",
        approval_id="app001",
        symbol="NKE",
        trade_date="2026-06-12",
        structure_type=AllowedPlaybook.BULL_CALL_SPREAD.value,
        order_class="mleg",
        order_type="limit",
        time_in_force="day",
        qty=1,
        limit_price=0.14,
        max_loss=0.14,
        max_profit=0.36,
        reward_risk=2.5,
        pmp=0.33,
        pmp_source="x",
        pmp_confidence="LOW",
        expected_value=0.02,
        long_leg_symbol="NKE260618C00047000",
        short_leg_symbol="NKE260618C00047500",
        long_leg_side="buy",
        short_leg_side="sell",
        long_leg_qty=1,
        short_leg_qty=1,
        expiration="2026-06-18",
        approval_status="APPROVED_FOR_PAPER_REVIEW",
        payload_status="PAPER_PAYLOAD_READY",
        payload_reason="ok",
        failure_reasons="",
        provenance="payload_c1_paper_candidate",
    )
    base.update(overrides)
    return PaperPayloadCandidate(**base)  # type: ignore[arg-type]


def test_leg_mid_from_bid_ask() -> None:
    assert leg_mid_from_bid_ask(0.08, 0.10) == 0.09
    assert leg_mid_from_bid_ask(None, 0.10) is None
    assert leg_mid_from_bid_ask(0.12, 0.10) is None


def test_debit_spread_close_mid() -> None:
    assert (
        calculate_spread_close_mid(
            AllowedPlaybook.BULL_CALL_SPREAD.value,
            long_leg_mid=0.50,
            short_leg_mid=0.41,
        )
        == pytest.approx(0.09)
    )
    assert (
        calculate_spread_close_mid(
            AllowedPlaybook.BEAR_PUT_SPREAD.value,
            long_leg_mid=0.50,
            short_leg_mid=0.41,
        )
        == pytest.approx(0.09)
    )


def test_credit_spread_close_mid() -> None:
    assert (
        calculate_spread_close_mid(
            AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value,
            long_leg_mid=0.20,
            short_leg_mid=0.35,
        )
        == pytest.approx(0.15)
    )


def test_explicit_limit_does_not_fetch_quotes() -> None:
    def fail_fetch(_symbols: tuple[str, ...]) -> dict[str, OptionLegQuote]:
        raise AssertionError("quote fetch should not run for explicit limit")

    result = price_spread_close(
        _payload(),
        explicit_limit_price=0.09,
        quote_fetch_fn=fail_fetch,
    )
    assert result.close_price_status == "EXPLICIT"
    assert result.quote_fetch_attempted is False
    assert result.suggested_close_limit == 0.09


def test_quote_mid_available_from_fetch_fn() -> None:
    def fake_fetch(symbols: tuple[str, ...]) -> dict[str, OptionLegQuote]:
        return {
            symbols[0]: OptionLegQuote(symbols[0], 0.48, 0.52, 0.50),
            symbols[1]: OptionLegQuote(symbols[1], 0.39, 0.43, 0.41),
        }

    result = price_spread_close(_payload(), quote_fetch_fn=fake_fetch)
    assert result.quote_fetch_attempted is True
    assert result.close_price_status == "AVAILABLE"
    assert result.close_price_source == "quote_mid"
    assert result.spread_mid == pytest.approx(0.09)
    assert result.suggested_close_limit == round_option_limit_price(0.09)


def test_missing_quotes_fail_closed() -> None:
    def empty_quotes(symbols: tuple[str, ...]) -> dict[str, OptionLegQuote]:
        return {sym: OptionLegQuote(sym, None, None, None) for sym in symbols}

    result = price_spread_close(_payload(), quote_fetch_fn=empty_quotes)
    assert result.close_price_status == "MISSING_QUOTES"
    assert result.suggested_close_limit is None


def test_fetch_alpaca_option_latest_quotes_parses_dict() -> None:
    with patch("qops.execution.spread_close_pricing.resolve_market_data_api_keys", return_value=("k", "s")):
        with patch("alpaca.data.historical.option.OptionHistoricalDataClient") as mock_cls:
            mock_cls.return_value.get_option_latest_quote.return_value = {
                "OPT1": {"bp": 1.0, "ap": 1.2},
            }
            quotes = fetch_alpaca_option_latest_quotes(("OPT1",))
    assert quotes["OPT1"].mid == pytest.approx(1.1)
