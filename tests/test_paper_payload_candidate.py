"""PAYLOAD-C1: paper payload candidate layer."""

from __future__ import annotations

from qops.execution.paper_payload_candidate import (
    ORDER_CLASS_MLEG,
    PaperApprovalInputRow,
    build_paper_payload_candidates,
    evaluate_paper_payload_candidate,
)
from qops.schemas.playbook import AllowedPlaybook


def _approved_row(**overrides: object) -> PaperApprovalInputRow:
    base = dict(
        approval_id="abc123approval",
        symbol="SPY",
        trade_date="2026-06-13",
        structure_type=AllowedPlaybook.BULL_CALL_SPREAD.value,
        long_leg_symbol="SPY260620C00420000",
        short_leg_symbol="SPY260620C00425000",
        expiration="2026-06-20",
        net_debit_or_credit=1.05,
        max_profit=3.95,
        max_loss=1.05,
        reward_risk=3.76,
        pmp=0.35,
        pmp_source="short_leg_delta_proxy",
        pmp_confidence="LOW",
        expected_value=0.10,
        approval_status="APPROVED_FOR_PAPER_REVIEW",
        failure_reasons="",
        suggested_contract_qty=1,
        provenance="approval_c1_paper_review",
    )
    base.update(overrides)
    return PaperApprovalInputRow(**base)  # type: ignore[arg-type]


def test_ready_from_approved_row() -> None:
    out = evaluate_paper_payload_candidate(_approved_row())
    assert out.payload_status == "PAPER_PAYLOAD_READY"
    assert out.qty == 1
    assert out.long_leg_qty == 1
    assert out.short_leg_qty == 1
    assert out.limit_price == 1.05
    assert out.order_class == ORDER_CLASS_MLEG
    assert out.order_type == "limit"
    assert out.time_in_force == "day"
    assert out.long_leg_side == "buy"
    assert out.short_leg_side == "sell"


def test_rejects_non_approved_input() -> None:
    out = evaluate_paper_payload_candidate(_approved_row(approval_status="REJECTED"))
    assert out.payload_status == "REJECTED"
    assert "approval_not_approved_for_paper_review" in out.failure_reasons


def test_incomplete_missing_approval_id() -> None:
    out = evaluate_paper_payload_candidate(_approved_row(approval_id=""))
    assert out.payload_status == "INCOMPLETE"


def test_rejects_non_positive_ev() -> None:
    out = evaluate_paper_payload_candidate(_approved_row(expected_value=0.0))
    assert out.payload_status == "REJECTED"
    assert "non_positive_expected_value" in out.failure_reasons


def test_credit_spread_leg_sides() -> None:
    out = evaluate_paper_payload_candidate(
        _approved_row(
            structure_type=AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value,
            long_leg_symbol="SPY260620P00400000",
            short_leg_symbol="SPY260620P00410000",
            net_debit_or_credit=0.85,
        )
    )
    assert out.payload_status == "PAPER_PAYLOAD_READY"
    assert out.long_leg_side == "buy"
    assert out.short_leg_side == "sell"


def test_build_batch() -> None:
    rows = [_approved_row(), _approved_row(approval_status="REJECTED")]
    built = build_paper_payload_candidates(rows)
    assert len(built) == 2
    assert sum(1 for b in built if b.payload_status == "PAPER_PAYLOAD_READY") == 1
