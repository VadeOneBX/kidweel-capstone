"""MCP-C12A: Alpaca paper transport bridge."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from qops.execution.alpaca_paper_bridge import (
    CANONICAL_PAPER_BASE_URL,
    AlpacaPaperCredentials,
    build_alpaca_mleg_order_request,
    deterministic_client_order_id,
    check_alpaca_paper_credentials,
    effective_transport_limit,
    filter_ready_payloads,
    normalize_paper_base_url,
    run_paper_payload_transport,
    submit_alpaca_paper_mleg_order,
    transport_error_raw,
    validate_paper_endpoint,
)
from qops.execution.mcp_response import normalize_mcp_response
from qops.execution.paper_payload_candidate import PaperPayloadCandidate
from qops.schemas.playbook import AllowedPlaybook


def _ready_payload(**overrides: object) -> PaperPayloadCandidate:
    base = dict(
        payload_id="pay001",
        approval_id="app001",
        symbol="SPY",
        trade_date="2026-06-13",
        structure_type=AllowedPlaybook.BULL_CALL_SPREAD.value,
        order_class="mleg",
        order_type="limit",
        time_in_force="day",
        qty=1,
        limit_price=1.05,
        max_loss=1.05,
        max_profit=3.95,
        reward_risk=3.76,
        pmp=0.35,
        pmp_source="short_leg_delta_proxy",
        pmp_confidence="LOW",
        expected_value=0.10,
        long_leg_symbol="SPY260620C00420000",
        short_leg_symbol="SPY260620C00425000",
        long_leg_side="buy",
        short_leg_side="sell",
        long_leg_qty=1,
        short_leg_qty=1,
        expiration="2026-06-20",
        approval_status="APPROVED_FOR_PAPER_REVIEW",
        payload_status="PAPER_PAYLOAD_READY",
        payload_reason="paper_payload_fields_valid",
        failure_reasons="",
        provenance="payload_c1_paper_candidate",
    )
    base.update(overrides)
    return PaperPayloadCandidate(**base)  # type: ignore[arg-type]


def test_filter_only_ready() -> None:
    rows = [_ready_payload(), _ready_payload(payload_status="REJECTED")]
    assert len(filter_ready_payloads(rows)) == 1


def test_dry_run_does_not_call_alpaca() -> None:
    with patch(
        "qops.execution.alpaca_paper_bridge.submit_alpaca_paper_mleg_order",
    ) as mocked:
        results, fatal = run_paper_payload_transport([_ready_payload()], submit_paper=False)
        mocked.assert_not_called()
    assert fatal is None
    assert len(results) == 1
    assert results[0].transport_status == "PAPER_DRY_RUN_READY"
    assert results[0].dry_run is True


def test_missing_paper_endpoint_fails_validation() -> None:
    ok, detail = validate_paper_endpoint(None)
    assert not ok
    assert detail == "missing_paper_base_url"


def test_live_endpoint_fails() -> None:
    ok, detail = validate_paper_endpoint("https://api.alpaca.markets")
    assert not ok
    assert detail == "live_endpoint_forbidden"


def test_paper_endpoint_passes() -> None:
    ok, detail = validate_paper_endpoint(CANONICAL_PAPER_BASE_URL)
    assert ok
    assert detail == "paper_endpoint_ok"
    assert normalize_paper_base_url(f"{CANONICAL_PAPER_BASE_URL}/") == CANONICAL_PAPER_BASE_URL


def test_missing_credentials_fail_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPACA_PAPER_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_PAPER_SECRET_KEY", raising=False)
    monkeypatch.delenv("ALPACA_PAPER_BASE_URL", raising=False)
    results, fatal = run_paper_payload_transport([_ready_payload()], submit_paper=True, limit=1)
    assert fatal is not None
    assert results == []


def test_normalized_response_exact_five_keys() -> None:
    raw = {
        "accepted": True,
        "status": "accepted",
        "broker_mode": "paper",
        "external_order_id": "oid-1",
        "message": "ok",
    }
    normalized = normalize_mcp_response(raw)
    assert normalized.broker_mode == "paper"
    assert normalized.external_order_id == "oid-1"


def test_transport_error_raw_normalizes() -> None:
    raw = transport_error_raw("boom")
    normalized = normalize_mcp_response(raw)
    assert normalized.accepted is False
    assert normalized.message == "boom"


def test_submit_mode_defaults_limit_to_one() -> None:
    assert effective_transport_limit(submit_paper=True, limit=None) == 1
    assert effective_transport_limit(submit_paper=True, limit=5) == 5


def test_submit_uses_injected_fn() -> None:
    def fake_submit(
        _creds: AlpacaPaperCredentials,
        _payload: PaperPayloadCandidate,
    ) -> dict:
        return {
            "accepted": True,
            "status": "accepted",
            "broker_mode": "paper",
            "external_order_id": "paper-99",
            "message": "accepted",
        }

    creds = AlpacaPaperCredentials(
        api_key="k",
        secret_key="s",
        base_url=CANONICAL_PAPER_BASE_URL,
        env_pair_label="test",
    )
    with patch(
        "qops.execution.alpaca_paper_bridge.resolve_alpaca_paper_credentials",
        return_value=creds,
    ):
        results, fatal = run_paper_payload_transport(
            [_ready_payload()],
            submit_paper=True,
            limit=1,
            submit_fn=fake_submit,
        )
    assert fatal is None
    assert results[0].transport_status == "PAPER_SUBMITTED"
    assert results[0].external_order_id == "paper-99"


def test_build_mleg_request_debit_positive_limit() -> None:
    req = build_alpaca_mleg_order_request(_ready_payload())
    assert req.limit_price == 1.05
    assert len(req.legs) == 2
    assert req.client_order_id == deterministic_client_order_id(_ready_payload())


def test_build_mleg_request_credit_negative_limit() -> None:
    req = build_alpaca_mleg_order_request(
        _ready_payload(
            structure_type=AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value,
            limit_price=0.85,
        )
    )
    assert req.limit_price == -0.85


def test_env_check_ready_with_paper_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPACA_PAPER_API_KEY", "key")
    monkeypatch.setenv("ALPACA_PAPER_SECRET_KEY", "secret")
    monkeypatch.setenv("ALPACA_PAPER_BASE_URL", CANONICAL_PAPER_BASE_URL)
    check = check_alpaca_paper_credentials()
    assert check.credential_status == "READY"
    assert check.endpoint_ok is True


def test_non_ready_not_in_dry_run_results() -> None:
    results, _ = run_paper_payload_transport(
        [_ready_payload(payload_status="REJECTED")],
        submit_paper=False,
    )
    assert results == []


@patch("alpaca.trading.client.TradingClient")
def test_submit_alpaca_paper_mleg_order_maps_response(mock_client_cls: MagicMock) -> None:
    from alpaca.trading.enums import OrderStatus

    order = MagicMock()
    order.id = "abc"
    order.status = OrderStatus.ACCEPTED
    mock_client_cls.return_value.submit_order.return_value = order

    creds = AlpacaPaperCredentials(
        api_key="k",
        secret_key="s",
        base_url=CANONICAL_PAPER_BASE_URL,
        env_pair_label="ALPACA_PAPER_*",
    )
    raw = submit_alpaca_paper_mleg_order(creds, _ready_payload())
    normalize_mcp_response(raw)
    mock_client_cls.assert_called_once()
    call_kwargs = mock_client_cls.call_args.kwargs
    assert call_kwargs["paper"] is True
    assert call_kwargs["url_override"] == CANONICAL_PAPER_BASE_URL
