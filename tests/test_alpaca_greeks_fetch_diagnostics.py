from __future__ import annotations

from qops.backtest.alpaca_blueprint_adapter import AlpacaBlueprintReplayPlanRow
from qops.backtest.alpaca_greeks_layer import (
    GreeksFetchDiagnostics,
    resolve_fetch_failure_class,
    stage_greeks_for_plans,
    validate_blueprint_for_chain_request,
)


def _valid_plan(**overrides: object) -> AlpacaBlueprintReplayPlanRow:
    base = dict(
        symbol="SPY",
        trade_date="2026-04-14",
        current_price=500.0,
        dte_min=0,
        dte_max=7,
        expiration_window="2026-04-14..2026-04-21",
        strike_lower_bound=485.0,
        strike_upper_bound=515.0,
        request_reason="test",
        source_profile="test",
        has_spy_context=True,
        provenance="test",
        databento_next_step="skip",
    )
    base.update(overrides)
    return AlpacaBlueprintReplayPlanRow(**base)  # type: ignore[arg-type]


def test_validate_blueprint_rejects_missing_symbol() -> None:
    ok, reason = validate_blueprint_for_chain_request(_valid_plan(symbol=""))
    assert ok is False
    assert reason == "missing_symbol"


def test_resolve_empty_fetch_result() -> None:
    diag = GreeksFetchDiagnostics(
        fetch_attempted=True,
        blueprint_rows=1,
        requests_attempted=1,
        requests_empty=1,
        requests_error=0,
        requests_invalid=0,
        contracts_before_filter=0,
        contracts_removed_by_filter=0,
        contracts_after_filter=0,
        contracts_staged=0,
        request_descriptors=(),
        empty_response_reasons=("SPY:alpaca_returned_zero_contracts",),
        error_summaries=(),
        failure_class=None,
    )
    assert resolve_fetch_failure_class(diag) == "EMPTY_FETCH_RESULT"


def test_stage_reports_empty_alpaca_response() -> None:
    class EmptyChainClient:
        def get_option_chain(self, _request: object) -> dict[str, object]:
            return {}

    plan = _valid_plan()
    rows, attempted, diag = stage_greeks_for_plans(
        [plan],
        fetch=True,
        client=EmptyChainClient(),
        risk_free_rate=0.05,
        allow_bs_fallback=False,
        fallback_volatility_proxy=None,
        min_time_to_expiry_days=None,
    )
    assert attempted is True
    assert rows == []
    assert diag is not None
    assert diag.requests_attempted == 1
    assert diag.requests_empty == 1
    assert diag.failure_class == "EMPTY_FETCH_RESULT"
