"""AM note gate, dealer structure, and spread skeptic (AM-NOTE-GATE-C1)."""

from __future__ import annotations

import json
from dataclasses import asdict

import pandas as pd

from qops.advisory.am_note_gate import (
    PAPER_GATE_AM_NOTE_INCOMPLETE,
    apply_am_note_paper_gate_to_audit,
    build_macro_paper_gate,
    resolve_am_note_status,
)
from qops.advisory.dealer_structure import assess_dealer_structure
from qops.advisory.spread_skeptic import build_spread_skeptic_note
from qops.risk.guard_runner import run_risk_guard
from qops.risk.paper_approval import SpreadCandidateInputRow
from qops.schemas.candidate_loop import SpreadExpressionStatus


def _passing_spread_row(**overrides: object) -> SpreadCandidateInputRow:
    base = dict(
        structure_type="BULL_CALL_SPREAD",
        underlying_symbol="IBIT",
        trade_date="2026-06-23",
        expiration="2026-06-27",
        long_option_symbol="IBIT260627C00036500",
        short_option_symbol="IBIT260627C00037000",
        spread_width=0.5,
        net_debit_or_credit=0.12,
        pmp_for_gate=0.35,
        pmp_source="short_leg_delta_proxy",
        pmp_confidence="LOW",
        max_profit=0.38,
        max_loss=0.12,
        reward_risk=3.16,
        break_even=36.62,
        capital_at_risk=0.12,
        passes_spread_math_gate=True,
        probability_status="PASS",
        ev_status="PASS",
        candidate_pass=True,
        failure_reasons="",
        provenance="test",
    )
    base.update(overrides)
    return SpreadCandidateInputRow(**base)  # type: ignore[arg-type]


def test_macro_gate_withholds_without_am_note(tmp_path: Path) -> None:
    gate = build_macro_paper_gate(tmp_path, run_id="2026-06-23-manual")
    assert gate.am_note_status == "NOT_AVAILABLE"
    assert gate.macro_context_state == "PRE_AM_NOTE_CONTEXT_INCOMPLETE"
    assert gate.am_note_required_before_paper is True
    assert gate.paper_approval_allowed is False
    assert "incomplete" in gate.macro_context_summary.lower()


def test_parse_am_note_json_example(tmp_path: Path) -> None:
    note = {
        "trade_date": "2026-06-23",
        "market_direction_summary": "Markets are selling off sharply after overnight weakness.",
        "overnight_risk_summary": "A 10% KOSPI crash triggered broad weakness.",
        "dealer_support_summary": "Dealer long gamma near the 7,200 area may slow downside.",
        "dealer_risk_summary": "If institutional short puts are closed, downside could accelerate.",
        "advisory_bias": "defensive",
        "spread_posture": "retain candidates, challenge long-delta spreads",
        "macro_catalysts": ["MU earnings", "Core PCE inflation report"],
        "call_positioning_risk": "Extreme short-dated call positioning remains volatile.",
    }
    path = tmp_path / "2026-06-23_morning_regime.json"
    path.write_text(json.dumps(note), encoding="utf-8")
    status, parsed = resolve_am_note_status([path], session_date="2026-06-23", override=None)
    assert status == "PARSED"
    assert parsed is not None
    assert parsed.advisory_bias == "defensive"
    assert len(parsed.macro_catalysts) == 2


def test_apply_paper_gate_downgrades_approval(tmp_path: Path) -> None:
    gate = build_macro_paper_gate(tmp_path, run_id="2026-06-23-manual")
    audit = pd.DataFrame(
        [
            {
                "paper_approval_status": "APPROVED_FOR_PAPER_REVIEW",
                "classification": "APPROVED_PAPER",
                "reject_reason": "",
            }
        ]
    )
    out = apply_am_note_paper_gate_to_audit(audit, gate)
    assert out.iloc[0]["classification"] == "PAPER_GATE_WITHHELD"
    assert out.iloc[0]["reject_reason"] == PAPER_GATE_AM_NOTE_INCOMPLETE


def test_spread_candidate_guard_applies_am_note_gate(tmp_path: Path) -> None:
    candidates = tmp_path / "spread_candidates.csv"
    row = _passing_spread_row()
    pd.DataFrame([asdict(row)]).to_csv(candidates, index=False)

    result = run_risk_guard(
        tmp_path,
        run_id="2026-06-23-test",
        candidates_artifact=str(candidates),
    )
    audit = pd.read_csv(result.risk_audit_artifact)
    assert audit.iloc[0]["classification"] == "PAPER_GATE_WITHHELD"
    assert audit.iloc[0]["reject_reason"] == PAPER_GATE_AM_NOTE_INCOMPLETE


def test_manual_override_allows_paper_gate(tmp_path: Path) -> None:
    override_dir = tmp_path / "data/advisory"
    override_dir.mkdir(parents=True)
    (override_dir / "2026-06-23-test_macro_context_override.json").write_text(
        json.dumps({"manual_override": True, "macro_context_state": "MANUAL_CONTEXT_OVERRIDE"}),
        encoding="utf-8",
    )
    gate = build_macro_paper_gate(tmp_path, run_id="2026-06-23-test")
    assert gate.paper_approval_allowed is True
    assert gate.macro_context_state == "MANUAL_CONTEXT_OVERRIDE"


def test_dealer_structure_negative_gamma(tmp_path: Path) -> None:
    context = pd.DataFrame(
        [
            {
                "symbol": "SPY",
                "trade_date": "2026-06-22",
                "gamma_ratio": 1.2,
                "iv_rank": 40.0,
                "notes": "current_price=600|call_wall=610|put_wall=590|hedge_wall=595|one_month_iv=0.2|one_month_rv=0.18",
                "source_profile": "spy_excel",
            },
            {
                "symbol": "SPY",
                "trade_date": "2026-06-23",
                "gamma_ratio": 0.85,
                "iv_rank": 45.0,
                "notes": "current_price=590|call_wall=605|put_wall=580|hedge_wall=595|one_month_iv=0.22|one_month_rv=0.19",
                "source_profile": "spy_excel",
            },
        ]
    )
    assessment = assess_dealer_structure(context)
    assert assessment.gamma_regime == "NEGATIVE_GAMMA_UNSTABLE"
    assert assessment.advisory_bias == "DEFENSIVE"


def test_spread_skeptic_ibit_frontier_language() -> None:
    row = pd.Series(
        {
            "expression_id": "ibit-wide",
            "symbol": "IBIT",
            "expression_status": SpreadExpressionStatus.ALTERNATE.value,
            "structure": "BULL_CALL_SPREAD",
            "long_strike": 36.5,
            "short_strike": 39.0,
            "rr_actual": 6.0,
            "breakeven": 37.0,
            "debit": 0.12,
            "max_profit": 2.38,
            "bid_ask_quality": "POOR",
            "width": 2.5,
            "short_leg_bid": 0.01,
            "short_leg_ask_spread_pct": 66.67,
        }
    )
    note = build_spread_skeptic_note(
        row,
        primary_rr=3.0,
        macro_posture="defensive",
        spot=36.0,
        wider_alternate_exists=False,
    )
    assert note.spread_skeptic_flag is True
    assert "materially higher reward/risk" in note.interesting_because
    assert "thin" in note.but_challenge.lower() or "liquidity" in note.but_challenge.lower()
    assert "frontier" in note.promotion_condition.lower()


def test_spread_skeptic_primary_not_optimal_language() -> None:
    row = pd.Series(
        {
            "expression_id": "ibit-narrow",
            "symbol": "IBIT",
            "expression_status": SpreadExpressionStatus.PRIMARY.value,
            "structure": "BULL_CALL_SPREAD",
            "long_strike": 36.5,
            "short_strike": 37.0,
            "rr_actual": 3.0,
            "breakeven": 36.62,
            "debit": 0.12,
            "max_profit": 0.38,
            "bid_ask_quality": "PASS",
            "width": 0.5,
        }
    )
    note = build_spread_skeptic_note(
        row,
        primary_rr=3.0,
        macro_posture="context incomplete; paper approval withheld",
        spot=36.0,
        wider_alternate_exists=True,
    )
    assert "dealer-aligned" in note.interesting_because
    assert "macro context gate" in note.but_challenge.lower() or "AM note" in note.but_challenge
    assert note.spread_skeptic_flag is True
