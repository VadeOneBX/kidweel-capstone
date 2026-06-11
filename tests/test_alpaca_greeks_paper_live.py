from __future__ import annotations

from datetime import date

from qops.backtest.alpaca_greeks_layer import (
    PAPER_LIVE_MODE,
    PaperLiveSymbolSpec,
    _today_trade_date,
    build_paper_live_blueprint_plans,
)


def test_paper_live_plan_uses_today_and_current_exp_window() -> None:
    specs = [
        PaperLiveSymbolSpec(
            symbol="AAPL",
            current_price=200.0,
            source_profile="explicit_symbol",
            has_spy_context=False,
            provenance="test",
        )
    ]
    plans = build_paper_live_blueprint_plans(
        specs,
        dte_min=0,
        dte_max=14,
        strike_buffer_pct=0.03,
        fetch_prices=False,
        option_client=None,
    )
    assert len(plans) == 1
    plan = plans[0]
    assert plan.trade_date == _today_trade_date()
    assert plan.trade_date == date.today().isoformat()
    assert plan.dte_min == 0
    assert plan.dte_max == 14
    assert plan.symbol == "AAPL"
    assert plan.expiration_window.startswith(plan.trade_date)


def test_paper_live_mode_constant() -> None:
    assert PAPER_LIVE_MODE == "paper_live"
