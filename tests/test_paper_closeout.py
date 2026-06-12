from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from qops.execution.alpaca_paper_bridge import (
    CANONICAL_PAPER_BASE_URL,
    AlpacaPaperCredentials,
    sanitize_alpaca_mleg_order_request,
    validate_paper_endpoint,
)
from qops.execution.paper_closeout import (
    FilledOrderStatusRow,
    QUOTE_BASED_CLOSE_PRICE_IMPLEMENTED,
    build_alpaca_close_mleg_order_request,
    deterministic_close_client_order_id,
    filter_filled_order_status_rows,
    load_paper_order_status_audit_rows,
    resolve_spread_close_pricing,
    run_paper_closeout,
    submit_alpaca_paper_close_mleg_order,
)
from qops.execution.paper_payload_candidate import PaperPayloadCandidate
from qops.execution.paper_position_audit import BrokerPositionSnapshot
from qops.execution.spread_close_pricing import OptionLegQuote
from qops.schemas.playbook import AllowedPlaybook


def _status_row(**overrides: object) -> FilledOrderStatusRow:
    base = {
        "payload_id": "pay001",
        "approval_id": "app001",
        "external_order_id": "open-oid",
        "current_status": "filled",
        "filled_qty": "1",
        "filled_avg_price": "0.12",
        "failure_reasons": "",
    }
    base.update(overrides)
    return FilledOrderStatusRow(**base)  # type: ignore[arg-type]


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
        pmp_source="short_leg_delta_proxy",
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
        payload_reason="paper_payload_fields_valid",
        failure_reasons="",
        provenance="payload_c1_paper_candidate",
    )
    base.update(overrides)
    return PaperPayloadCandidate(**base)  # type: ignore[arg-type]


def _quote_fetch(symbols: tuple[str, ...]) -> dict[str, OptionLegQuote]:
    return {
        symbols[0]: OptionLegQuote(symbols[0], 0.48, 0.52, 0.50),
        symbols[1]: OptionLegQuote(symbols[1], 0.39, 0.43, 0.41),
    }


def _confirmed_positions() -> dict[str, object]:
    return {
        "ok": True,
        "failure_reasons": "",
        "positions": [
            BrokerPositionSnapshot("NKE260618C00047000", "1", "long"),
            BrokerPositionSnapshot("NKE260618C00047500", "1", "short"),
        ],
    }


def test_filter_rejects_non_filled() -> None:
    rows = filter_filled_order_status_rows([_status_row(current_status="pending_new")])
    assert rows == []


def test_deterministic_close_client_order_id() -> None:
    assert deterministic_close_client_order_id("0eb54452ad35bb44") == (
        "qops-paper-close-0eb54452ad35bb44"
    )
    assert deterministic_close_client_order_id("0eb54452ad35bb44", attempt=2) == (
        "qops-paper-close-0eb54452ad35bb44-a2"
    )


def test_resolve_close_attempt_from_prior_results(tmp_path: Path) -> None:
    from qops.execution.paper_closeout import resolve_close_client_order_attempt

    csv_path = tmp_path / "closeout.csv"
    csv_path.write_text(
        "payload_id,approval_id,original_external_order_id,close_status\n"
        "0eb54452ad35bb44,a1,oid,PAPER_CLOSE_REJECTED\n",
        encoding="utf-8",
    )
    assert (
        resolve_close_client_order_attempt(
            "0eb54452ad35bb44",
            results_path=csv_path,
        )
        == 2
    )


def test_close_mleg_has_no_parent_symbol_and_two_legs() -> None:
    req = build_alpaca_close_mleg_order_request(_payload(), limit_price=0.10)
    assert req.symbol is None
    assert len(req.legs) == 2
    sanitized = sanitize_alpaca_mleg_order_request(req)
    assert "symbol" not in sanitized


def test_close_legs_use_to_close_intents() -> None:
    req = build_alpaca_close_mleg_order_request(_payload(), limit_price=0.10)
    long_leg, short_leg = req.legs
    assert long_leg.side.value == "sell"
    assert long_leg.position_intent.value == "sell_to_close"
    assert short_leg.side.value == "buy"
    assert short_leg.position_intent.value == "buy_to_close"


def test_resolve_spread_close_pricing_explicit_and_quote_mid() -> None:
    payload = _payload()
    explicit = resolve_spread_close_pricing(payload, explicit_limit_price=0.15)
    assert explicit.suggested_close_limit == 0.15
    assert explicit.close_price_status == "EXPLICIT"
    quoted = resolve_spread_close_pricing(payload, quote_fetch_fn=_quote_fetch)
    assert quoted.close_price_status == "AVAILABLE"
    assert quoted.suggested_close_limit == 0.09
    assert QUOTE_BASED_CLOSE_PRICE_IMPLEMENTED is True


def test_dry_run_does_not_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPACA_PAPER_API_KEY", "key")
    monkeypatch.setenv("ALPACA_PAPER_SECRET_KEY", "secret")
    monkeypatch.setenv("ALPACA_PAPER_BASE_URL", CANONICAL_PAPER_BASE_URL)

    with patch(
        "qops.execution.paper_closeout.submit_alpaca_paper_close_mleg_order"
    ) as mocked_submit:
        results, fatal = run_paper_closeout(
            [_status_row()],
            [_payload()],
            close_paper=False,
            get_positions_fn=lambda _c: _confirmed_positions(),
            quote_fetch_fn=_quote_fetch,
        )
        mocked_submit.assert_not_called()
    assert fatal is None
    assert results[0].close_status == "PAPER_CLOSE_DRY_RUN_READY"


def test_submit_requires_close_paper_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPACA_PAPER_API_KEY", "key")
    monkeypatch.setenv("ALPACA_PAPER_SECRET_KEY", "secret")
    monkeypatch.setenv("ALPACA_PAPER_BASE_URL", CANONICAL_PAPER_BASE_URL)

    with patch(
        "qops.execution.paper_closeout.submit_alpaca_paper_close_mleg_order"
    ) as mocked_submit:
        run_paper_closeout(
            [_status_row()],
            [_payload()],
            close_paper=False,
            limit_price=0.10,
            get_positions_fn=lambda _c: _confirmed_positions(),
            quote_fetch_fn=_quote_fetch,
        )
        mocked_submit.assert_not_called()


def test_submit_requires_limit_when_quotes_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPACA_PAPER_API_KEY", "key")
    monkeypatch.setenv("ALPACA_PAPER_SECRET_KEY", "secret")
    monkeypatch.setenv("ALPACA_PAPER_BASE_URL", CANONICAL_PAPER_BASE_URL)

    def missing(_symbols: tuple[str, ...]) -> dict[str, OptionLegQuote]:
        return {sym: OptionLegQuote(sym, None, None, None) for sym in _symbols}

    with patch(
        "qops.execution.paper_closeout.submit_alpaca_paper_close_mleg_order"
    ) as mocked_submit:
        results, _ = run_paper_closeout(
            [_status_row()],
            [_payload()],
            close_paper=True,
            limit_price=None,
            get_positions_fn=lambda _c: _confirmed_positions(),
            quote_fetch_fn=missing,
        )
        mocked_submit.assert_not_called()
    assert results[0].close_status == "PAPER_CLOSE_ERROR"
    assert results[0].failure_reasons == "missing_bid_ask_mid"


def test_submit_requires_paper_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPACA_PAPER_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_PAPER_SECRET_KEY", raising=False)
    monkeypatch.delenv("ALPACA_PAPER_BASE_URL", raising=False)
    with patch("qops.execution.alpaca_paper_bridge.load_local_env", return_value=False):
        results, fatal = run_paper_closeout(
            [_status_row()],
            [_payload()],
            close_paper=True,
            limit_price=0.10,
            get_positions_fn=lambda _c: _confirmed_positions(),
            quote_fetch_fn=_quote_fetch,
        )
    assert fatal == "paper_credentials_not_ready"
    assert results == []


def test_missing_payload_skipped() -> None:
    results, _ = run_paper_closeout([_status_row()], [], get_positions_fn=lambda _c: _confirmed_positions())
    assert results[0].close_status == "PAPER_CLOSE_SKIPPED"


def test_legs_must_match_positions() -> None:
    def empty_positions(_c: AlpacaPaperCredentials) -> dict[str, object]:
        return {"ok": True, "failure_reasons": "", "positions": []}

    results, _ = run_paper_closeout(
        [_status_row()],
        [_payload()],
        get_positions_fn=empty_positions,
    )
    assert results[0].close_status == "PAPER_CLOSE_ERROR"
    assert "position" in results[0].message


def test_live_endpoint_rejected_on_submit() -> None:
    creds = AlpacaPaperCredentials(
        api_key="k",
        secret_key="s",
        base_url="https://api.alpaca.markets",
        env_pair_label="ALPACA_PAPER_*",
    )
    raw = submit_alpaca_paper_close_mleg_order(creds, object())
    assert raw["accepted"] is False
    ok, detail = validate_paper_endpoint("https://api.alpaca.markets")
    assert ok is False
    assert detail == "live_endpoint_forbidden"


def test_load_status_audit_csv(tmp_path: Path) -> None:
    path = tmp_path / "status.csv"
    path.write_text(
        "payload_id,approval_id,external_order_id,current_status,filled_qty,filled_avg_price,failure_reasons\n"
        "p1,a1,e1,filled,1,0.12,\n",
        encoding="utf-8",
    )
    rows = load_paper_order_status_audit_rows(path)
    assert len(rows) == 1
    assert rows[0].current_status == "filled"


def test_close_submit_calls_submit_order_only() -> None:
    creds = AlpacaPaperCredentials(
        api_key="k",
        secret_key="s",
        base_url=CANONICAL_PAPER_BASE_URL,
        env_pair_label="ALPACA_PAPER_*",
    )
    request = build_alpaca_close_mleg_order_request(_payload(), limit_price=0.11)
    with patch("alpaca.trading.client.TradingClient") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        order = MagicMock()
        order.id = "close-oid"
        order.status = "pending_new"
        client.submit_order.return_value = order
        raw = submit_alpaca_paper_close_mleg_order(creds, request)
        client.submit_order.assert_called_once()
        client.close_position.assert_not_called()
        client.close_all_positions.assert_not_called()
        assert raw["external_order_id"] == "close-oid"
