"""APPROVAL-C1: paper approval candidate layer."""

from __future__ import annotations

from qops.risk.paper_approval import (
    SpreadCandidateInputRow,
    build_paper_approval_candidates,
    evaluate_paper_approval,
)
from qops.schemas.playbook import AllowedPlaybook


def _passing_row(**overrides: object) -> SpreadCandidateInputRow:
    base = dict(
        structure_type=AllowedPlaybook.BULL_CALL_SPREAD.value,
        underlying_symbol="SPY",
        trade_date="2026-06-13",
        expiration="2026-06-20",
        long_option_symbol="SPY260620C00420000",
        short_option_symbol="SPY260620C00425000",
        spread_width=5.0,
        net_debit_or_credit=1.05,
        pmp_for_gate=0.35,
        pmp_source="short_leg_delta_proxy",
        pmp_confidence="LOW",
        max_profit=3.95,
        max_loss=1.05,
        reward_risk=3.76,
        break_even=421.05,
        capital_at_risk=1.05,
        passes_spread_math_gate=True,
        probability_status="PASS",
        ev_status="PASS",
        candidate_pass=True,
        failure_reasons="",
        provenance="struct_c2",
    )
    base.update(overrides)
    return SpreadCandidateInputRow(**base)  # type: ignore[arg-type]


def test_approves_candidate_pass_row() -> None:
    out = evaluate_paper_approval(_passing_row(), max_risk=600.0)
    assert out.approval_status == "APPROVED_FOR_PAPER_REVIEW"
    assert out.suggested_contract_qty == 1
    assert out.risk_unit == 1.05
    assert out.pmp == 0.35


def test_rejects_not_candidate_pass() -> None:
    out = evaluate_paper_approval(_passing_row(candidate_pass=False), max_risk=600.0)
    assert out.approval_status == "REJECTED"
    assert "not_candidate_pass" in out.failure_reasons


def test_incomplete_missing_pmp() -> None:
    out = evaluate_paper_approval(_passing_row(pmp_for_gate=None, candidate_pass=False), max_risk=600.0)
    assert out.approval_status == "INCOMPLETE"


def test_rejects_max_loss_over_max_risk() -> None:
    out = evaluate_paper_approval(_passing_row(max_loss=800.0, capital_at_risk=800.0), max_risk=600.0)
    assert out.approval_status == "REJECTED"
    assert "max_loss_exceeds_max_risk" in out.failure_reasons


def test_rejects_non_positive_ev() -> None:
    out = evaluate_paper_approval(_passing_row(ev_status="WATCH"), max_risk=600.0)
    assert out.approval_status == "REJECTED"


def test_build_batch() -> None:
    rows = [_passing_row(), _passing_row(candidate_pass=False)]
    built = build_paper_approval_candidates(rows, max_risk=600.0)
    assert len(built) == 2
    assert sum(1 for b in built if b.approval_status == "APPROVED_FOR_PAPER_REVIEW") == 1
