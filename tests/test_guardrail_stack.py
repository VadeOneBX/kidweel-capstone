"""OPENAI-AGENTS-GUARDRAIL-STACK-C1 tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from qops.execution.alpaca_paper_bridge import (
    CANONICAL_PAPER_BASE_URL,
    AlpacaPaperCredentials,
    run_paper_payload_transport,
)
from qops.execution.hitl_paper_transport import (
    apply_operator_decision,
    evaluate_paper_transport_hitl,
    hitl_root,
    load_or_create_approval,
)
from qops.execution.paper_payload_candidate import PaperPayloadCandidate
from qops.guardrails.base import (
    STATUS_EV_REJECTED,
    STATUS_LIVE_ENV_FORBIDDEN,
    STATUS_MALFORMED_PAYLOAD,
    STATUS_NEGATIVE_OR_ZERO_MAX_PROFIT,
    STATUS_PASS,
    STATUS_UNDEFINED_RISK_REJECTED,
    STATUS_WATCH_PENDING_REVIEW,
    GuardrailCandidate,
    evaluate_guardrails,
    guardrails_log_root,
)
from qops.guardrails.tool_payload import guardrail_candidate_from_paper_payload
from qops.schemas.hitl import STATUS_APPROVAL_REQUIRED
from qops.schemas.playbook import AllowedPlaybook


def _leg(
    *,
    side: str = "buy",
    option_type: str = "CALL",
    strike: float = 420.0,
    expiration: str = "2026-06-20",
    quantity: float = 1,
) -> dict:
    return {
        "side": side,
        "option_type": option_type,
        "strike": strike,
        "expiration": expiration,
        "quantity": quantity,
    }


def valid_bull_call_spread() -> GuardrailCandidate:
    return GuardrailCandidate(
        candidate_id="valid-bcs-001",
        symbol="SPY",
        structure=AllowedPlaybook.BULL_CALL_SPREAD.value,
        legs=[_leg(side="buy"), _leg(side="sell", strike=425.0)],
        max_loss=1.05,
        max_profit=3.95,
        rr_actual=3.76,
        pmp=0.35,
        ev=0.10,
    )


def live_env_candidate() -> GuardrailCandidate:
    base = valid_bull_call_spread()
    return GuardrailCandidate(
        candidate_id=base.candidate_id,
        symbol=base.symbol,
        structure=base.structure,
        legs=base.legs,
        max_loss=base.max_loss,
        max_profit=base.max_profit,
        rr_actual=base.rr_actual,
        pmp=base.pmp,
        ev=base.ev,
        live_env_hint=True,
    )


def missing_symbol_candidate() -> GuardrailCandidate:
    base = valid_bull_call_spread()
    return GuardrailCandidate(
        candidate_id=base.candidate_id,
        symbol="",
        structure=base.structure,
        legs=base.legs,
        max_loss=base.max_loss,
    )


def short_strangle_candidate() -> GuardrailCandidate:
    base = valid_bull_call_spread()
    return GuardrailCandidate(
        candidate_id="strangle-001",
        symbol=base.symbol,
        structure="SHORT_STRANGLE",
        legs=base.legs,
        max_loss=base.max_loss,
    )


def malformed_leg_candidate() -> GuardrailCandidate:
    return GuardrailCandidate(
        candidate_id="malformed-001",
        symbol="SPY",
        structure=AllowedPlaybook.BULL_CALL_SPREAD.value,
        legs=[
            {
                "side": "buy",
                "option_type": "CALL",
                "strike": -1.0,
                "expiration": "2026-06-20",
                "quantity": 1,
            }
        ],
        max_loss=1.0,
    )


def negative_ev_candidate() -> GuardrailCandidate:
    base = valid_bull_call_spread()
    return GuardrailCandidate(
        candidate_id="neg-ev-001",
        symbol=base.symbol,
        structure=base.structure,
        legs=base.legs,
        max_loss=base.max_loss,
        max_profit=base.max_profit,
        ev=-0.01,
    )


def zero_max_profit_candidate() -> GuardrailCandidate:
    base = valid_bull_call_spread()
    return GuardrailCandidate(
        candidate_id="zero-profit-001",
        symbol=base.symbol,
        structure=base.structure,
        legs=base.legs,
        max_loss=base.max_loss,
        max_profit=0.0,
    )


def watch_candidate() -> GuardrailCandidate:
    base = valid_bull_call_spread()
    return GuardrailCandidate(
        candidate_id="watch-001",
        symbol=base.symbol,
        structure=base.structure,
        legs=base.legs,
        max_loss=base.max_loss,
        max_profit=base.max_profit,
        rr_actual=base.rr_actual,
        pmp=base.pmp,
        ev=base.ev,
        watch_promotion_viable=True,
    )


def _paper_payload(**overrides: object) -> PaperPayloadCandidate:
    base = dict(
        payload_id="pay-gr-001",
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


def test_live_env_blocks_first(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ALPACA_LIVE_TRADE", "true")
    result = evaluate_guardrails(valid_bull_call_spread(), base_dir=tmp_path)
    assert result.status == STATUS_LIVE_ENV_FORBIDDEN
    assert not result.ok


def test_undefined_risk_rejected(tmp_path: Path) -> None:
    result = evaluate_guardrails(short_strangle_candidate(), base_dir=tmp_path)
    assert result.status == STATUS_UNDEFINED_RISK_REJECTED


def test_malformed_legs_rejected(tmp_path: Path) -> None:
    result = evaluate_guardrails(malformed_leg_candidate(), base_dir=tmp_path)
    assert result.status == STATUS_MALFORMED_PAYLOAD


def test_negative_ev_rejected(tmp_path: Path) -> None:
    result = evaluate_guardrails(negative_ev_candidate(), base_dir=tmp_path)
    assert result.status == STATUS_EV_REJECTED


def test_zero_max_profit_rejected(tmp_path: Path) -> None:
    result = evaluate_guardrails(zero_max_profit_candidate(), base_dir=tmp_path)
    assert result.status == STATUS_NEGATIVE_OR_ZERO_MAX_PROFIT


def test_watch_cannot_submit(tmp_path: Path) -> None:
    payload = _paper_payload(
        payload_id="watch-001",
        approval_status="WATCH_PENDING_OPERATOR",
    )
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
            [payload],
            submit_paper=True,
            base_dir=tmp_path,
        )
    assert fatal is None
    assert results[0].transport_status == "PAPER_SKIPPED"
    assert results[0].failure_reasons == STATUS_WATCH_PENDING_REVIEW
    assert list((hitl_root(tmp_path) / "pending").glob("*.json"))


def test_valid_candidate_reaches_hitl_boundary(tmp_path: Path) -> None:
    payload = _paper_payload()
    gr = evaluate_guardrails(guardrail_candidate_from_paper_payload(payload), base_dir=tmp_path)
    assert gr.status == STATUS_PASS
    gate = evaluate_paper_transport_hitl(
        payload,
        candidate_passed_existing_gates=True,
        base_dir=tmp_path,
    )
    assert gate.status == STATUS_APPROVAL_REQUIRED


def test_guardrail_audit_artifact_written(tmp_path: Path) -> None:
    evaluate_guardrails(missing_symbol_candidate(), base_dir=tmp_path)
    audits = list(guardrails_log_root(tmp_path).glob("*.json"))
    assert len(audits) == 1
    record = json.loads(audits[0].read_text(encoding="utf-8"))
    assert record["packet"] == "OPENAI-AGENTS-GUARDRAIL-STACK-C1"
    assert record["paper_submit_allowed"] is False


def test_invalid_candidate_never_reaches_approved_transport(tmp_path: Path) -> None:
    payload = _paper_payload(structure_type="SHORT_STRANGLE")
    load_or_create_approval(payload, base_dir=tmp_path)
    apply_operator_decision(payload.payload_id, "approve", "should not matter", base_dir=tmp_path)

    def fake_submit(_c, _p):
        raise AssertionError("submit must not run for guardrail reject")

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
            [payload],
            submit_paper=True,
            base_dir=tmp_path,
            submit_fn=fake_submit,
        )
    assert results[0].failure_reasons == STATUS_UNDEFINED_RISK_REJECTED


def test_watch_fixture_status(tmp_path: Path) -> None:
    result = evaluate_guardrails(watch_candidate(), base_dir=tmp_path)
    assert result.status == STATUS_WATCH_PENDING_REVIEW
