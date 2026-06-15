from __future__ import annotations

from pathlib import Path

import pytest

from qops.execution.alpaca_paper_bridge import (
    CANONICAL_PAPER_BASE_URL,
    AlpacaPaperCredentials,
)
from qops.execution.paper_order_status import (
    SubmittedTransportRow,
    filter_submitted_transport_rows,
    get_alpaca_paper_order_by_id,
    load_paper_transport_results,
    run_paper_order_status_audit,
)


def _submitted_row(**overrides: object) -> SubmittedTransportRow:
    base = {
        "payload_id": "pid",
        "approval_id": "aid",
        "external_order_id": "oid-1",
        "broker_mode": "paper",
        "previous_status": "pending_new",
        "submitted_at": "2026-06-12T00:00:00+00:00",
        "transport_status": "PAPER_SUBMITTED",
    }
    base.update(overrides)
    return SubmittedTransportRow(**base)  # type: ignore[arg-type]


def test_filter_submitted_requires_status_and_order_id() -> None:
    rows = [
        _submitted_row(),
        _submitted_row(transport_status="PAPER_DRY_RUN_READY"),
        _submitted_row(external_order_id=""),
    ]
    assert len(filter_submitted_transport_rows(rows)) == 1


def test_load_paper_transport_results_from_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "transport.csv"
    csv_path.write_text(
        "payload_id,approval_id,transport_status,external_order_id,broker_mode,status,submitted_at\n"
        "p1,a1,PAPER_SUBMITTED,e1,paper,pending_new,2026-01-01T00:00:00+00:00\n",
        encoding="utf-8",
    )
    loaded = load_paper_transport_results(csv_path)
    assert len(loaded) == 1
    assert loaded[0].external_order_id == "e1"
    assert loaded[0].previous_status == "pending_new"


def test_load_closeout_results_csv_for_status_audit(tmp_path: Path) -> None:
    csv_path = tmp_path / "closeout.csv"
    csv_path.write_text(
        "payload_id,approval_id,original_external_order_id,close_external_order_id,"
        "close_status,broker_mode,status,submitted_at\n"
        "p1,a1,open-oid,close-oid,PAPER_CLOSE_SUBMITTED,paper,pending_new,2026-01-01T00:00:00+00:00\n",
        encoding="utf-8",
    )
    loaded = load_paper_transport_results(csv_path)
    assert len(filter_submitted_transport_rows(loaded)) == 1
    assert loaded[0].external_order_id == "close-oid"


def test_run_audit_uses_injected_get_order_fn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPACA_PAPER_API_KEY", "key")
    monkeypatch.setenv("ALPACA_PAPER_SECRET_KEY", "secret")
    monkeypatch.setenv("ALPACA_PAPER_BASE_URL", CANONICAL_PAPER_BASE_URL)

    def fake_get(
        _creds: AlpacaPaperCredentials,
        external_order_id: str,
    ) -> dict[str, object]:
        assert external_order_id == "oid-1"
        return {
            "ok": True,
            "current_status": "filled",
            "filled_qty": "1",
            "filled_avg_price": "0.55",
            "status_message": "order_status:filled",
            "failure_reasons": "",
        }

    audits, fatal = run_paper_order_status_audit(
        [_submitted_row()],
        limit=1,
        get_order_fn=fake_get,
    )
    assert fatal is None
    assert len(audits) == 1
    assert audits[0].current_status == "filled"
    assert audits[0].previous_status == "pending_new"
    assert audits[0].filled_qty == "1"


def test_run_audit_no_submitted_rows_skips_credentials() -> None:
    audits, fatal = run_paper_order_status_audit(
        [_submitted_row(transport_status="PAPER_REJECTED")],
        limit=1,
    )
    assert fatal is None
    assert audits == []


def test_get_order_rejects_non_canonical_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    creds = AlpacaPaperCredentials(
        api_key="k",
        secret_key="s",
        base_url="https://api.alpaca.markets",
        env_pair_label="ALPACA_PAPER_*",
    )
    raw = get_alpaca_paper_order_by_id(creds, "oid")
    assert raw["ok"] is False
    assert raw["failure_reasons"] == "live_endpoint_forbidden"


def test_get_order_does_not_call_submit_or_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import MagicMock, patch

    creds = AlpacaPaperCredentials(
        api_key="k",
        secret_key="s",
        base_url=CANONICAL_PAPER_BASE_URL,
        env_pair_label="ALPACA_PAPER_*",
    )
    with patch("alpaca.trading.client.TradingClient") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        order = MagicMock()
        order.status = "pending_new"
        order.filled_qty = 0
        order.filled_avg_price = None
        client.get_order_by_id.return_value = order

        raw = get_alpaca_paper_order_by_id(creds, "oid-99")
        client.get_order_by_id.assert_called_once_with("oid-99")
        client.submit_order.assert_not_called()
        client.cancel_order_by_id.assert_not_called()
        client.replace_order_by_id.assert_not_called()
        assert raw["current_status"] == "pending_new"
