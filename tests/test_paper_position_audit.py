from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from qops.execution.alpaca_paper_bridge import (
    CANONICAL_PAPER_BASE_URL,
    AlpacaPaperCredentials,
)
from qops.execution.paper_position_audit import (
    BrokerPositionSnapshot,
    FilledOrderAuditInput,
    audit_one_filled_order,
    classify_position_status,
    filter_filled_order_audit_inputs,
    get_alpaca_paper_positions,
    load_filled_order_audit_inputs,
    run_paper_position_audit,
)


def _filled_input(**overrides: object) -> FilledOrderAuditInput:
    base = {
        "payload_id": "pid",
        "approval_id": "aid",
        "external_order_id": "oid",
        "symbol": "NKE",
        "structure_type": "BULL_CALL_SPREAD",
        "expected_long_leg_symbol": "NKE260612C00045000",
        "expected_short_leg_symbol": "NKE260612C00045500",
        "expected_long_leg_qty": 1,
        "expected_short_leg_qty": 1,
    }
    base.update(overrides)
    return FilledOrderAuditInput(**base)  # type: ignore[arg-type]


def test_classify_position_status() -> None:
    assert classify_position_status(long_found=True, short_found=True, audit_error=False) == (
        "POSITION_CONFIRMED"
    )
    assert classify_position_status(long_found=True, short_found=False, audit_error=False) == (
        "POSITION_PARTIAL"
    )
    assert classify_position_status(long_found=False, short_found=False, audit_error=False) == (
        "POSITION_NOT_FOUND"
    )
    assert classify_position_status(long_found=True, short_found=True, audit_error=True) == (
        "POSITION_AUDIT_ERROR"
    )


def test_audit_one_confirms_both_legs() -> None:
    positions = {
        "NKE260612C00045000": BrokerPositionSnapshot(
            symbol="NKE260612C00045000", qty="1", side="long"
        ),
        "NKE260612C00045500": BrokerPositionSnapshot(
            symbol="NKE260612C00045500", qty="1", side="short"
        ),
    }
    audit = audit_one_filled_order(
        _filled_input(),
        positions,
        fetch_ok=True,
        fetch_failure="",
    )
    assert audit.position_status == "POSITION_CONFIRMED"
    assert audit.long_leg_position_found is True
    assert audit.short_leg_position_found is True


def test_load_filled_rows_from_status_audit(tmp_path: Path) -> None:
    status_path = tmp_path / "status.csv"
    transport_path = tmp_path / "transport.csv"
    payload_path = tmp_path / "payload.csv"
    status_path.write_text(
        "payload_id,approval_id,external_order_id,current_status,failure_reasons\n"
        "p1,a1,e1,filled,\n"
        "p2,a2,e2,pending_new,\n",
        encoding="utf-8",
    )
    transport_path.write_text(
        "payload_id,approval_id,symbol,structure_type,transport_status,external_order_id\n"
        "p1,a1,NKE,BULL_CALL_SPREAD,PAPER_SUBMITTED,e1\n",
        encoding="utf-8",
    )
    payload_path.write_text(
        "payload_id,approval_id,symbol,trade_date,structure_type,order_class,order_type,"
        "time_in_force,qty,limit_price,max_loss,max_profit,reward_risk,pmp,pmp_source,"
        "pmp_confidence,expected_value,long_leg_symbol,short_leg_symbol,long_leg_side,"
        "short_leg_side,long_leg_qty,short_leg_qty,expiration,approval_status,"
        "payload_status,payload_reason,failure_reasons,provenance\n"
        "p1,a1,NKE,2026-06-12,BULL_CALL_SPREAD,mleg,limit,day,1,0.12,0.12,0.88,7.33,0.5,"
        "x,LOW,0,NKE260612C00045000,NKE260612C00045500,buy,sell,1,1,2026-06-12,"
        "APPROVED,PAPER_PAYLOAD_READY,,,x\n",
        encoding="utf-8",
    )
    rows, source = load_filled_order_audit_inputs(
        status_path,
        transport_path=transport_path,
        payload_candidates_path=payload_path,
    )
    assert source == "status_audit"
    assert len(rows) == 1
    assert rows[0].expected_long_leg_symbol == "NKE260612C00045000"


def test_load_fallback_transport_when_status_audit_missing(tmp_path: Path) -> None:
    transport_path = tmp_path / "transport.csv"
    payload_path = tmp_path / "payload.csv"
    transport_path.write_text(
        "payload_id,approval_id,symbol,structure_type,transport_status,external_order_id\n"
        "p1,a1,NKE,BULL_CALL_SPREAD,PAPER_SUBMITTED,e1\n",
        encoding="utf-8",
    )
    payload_path.write_text(
        "payload_id,approval_id,symbol,trade_date,structure_type,order_class,order_type,"
        "time_in_force,qty,limit_price,max_loss,max_profit,reward_risk,pmp,pmp_source,"
        "pmp_confidence,expected_value,long_leg_symbol,short_leg_symbol,long_leg_side,"
        "short_leg_side,long_leg_qty,short_leg_qty,expiration,approval_status,"
        "payload_status,payload_reason,failure_reasons,provenance\n"
        "p1,a1,NKE,2026-06-12,BULL_CALL_SPREAD,mleg,limit,day,1,0.12,0.12,0.88,7.33,0.5,"
        "x,LOW,0,LONG,SHT,buy,sell,1,1,2026-06-12,APPROVED,PAPER_PAYLOAD_READY,,,x\n",
        encoding="utf-8",
    )
    missing_status = tmp_path / "missing_status.csv"
    rows, source = load_filled_order_audit_inputs(
        missing_status,
        transport_path=transport_path,
        payload_candidates_path=payload_path,
    )
    assert source == "transport"
    assert len(rows) == 1


def test_run_audit_uses_injected_positions_fn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPACA_PAPER_API_KEY", "key")
    monkeypatch.setenv("ALPACA_PAPER_SECRET_KEY", "secret")
    monkeypatch.setenv("ALPACA_PAPER_BASE_URL", CANONICAL_PAPER_BASE_URL)

    def fake_get(_creds: AlpacaPaperCredentials) -> dict[str, object]:
        return {
            "ok": True,
            "failure_reasons": "",
            "positions": [
                BrokerPositionSnapshot("NKE260612C00045000", "1", "long"),
                BrokerPositionSnapshot("NKE260612C00045500", "1", "short"),
            ],
        }

    audits, fatal = run_paper_position_audit(
        [_filled_input()],
        limit=1,
        get_positions_fn=fake_get,
    )
    assert fatal is None
    assert audits[0].position_status == "POSITION_CONFIRMED"


def test_get_positions_does_not_call_close_or_submit() -> None:
    creds = AlpacaPaperCredentials(
        api_key="k",
        secret_key="s",
        base_url=CANONICAL_PAPER_BASE_URL,
        env_pair_label="ALPACA_PAPER_*",
    )
    with patch("alpaca.trading.client.TradingClient") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        pos_long = MagicMock()
        pos_long.symbol = "NKE260612C00045000"
        pos_long.qty = 1
        pos_long.side = "long"
        client.get_all_positions.return_value = [pos_long]

        raw = get_alpaca_paper_positions(creds)
        client.get_all_positions.assert_called_once()
        client.submit_order.assert_not_called()
        client.cancel_order_by_id.assert_not_called()
        client.close_position.assert_not_called()
        client.close_all_positions.assert_not_called()
        assert raw["ok"] is True


def test_filter_requires_external_order_id() -> None:
    rows = filter_filled_order_audit_inputs([_filled_input(external_order_id="")])
    assert rows == []
