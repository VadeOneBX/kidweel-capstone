"""EXPRESSION-FRONTIER-C1 advisory review."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from qops.advisory.expression_frontier import (
    PAPER_GATE_FRONTIER_REVIEW,
    apply_frontier_paper_gate_to_audit,
    build_expression_frontier,
    manual_frontier_path,
)
from qops.advisory.run_advisory import build_run_advisory
from qops.runtime.orb_manifest import OrbRunManifest
from qops.schemas.candidate_loop import SpreadExpressionStatus


def _ibit_run_expressions() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "run_id": "2026-06-23-manual-091340",
                "expression_id": "IBIT:primary",
                "symbol": "IBIT",
                "expiration": "2026-06-26",
                "structure": "BULL_CALL_SPREAD",
                "expression_status": SpreadExpressionStatus.PRIMARY.value,
                "long_strike": 36.5,
                "short_strike": 37.0,
                "width": 0.5,
                "debit": 0.21,
                "max_profit": 0.29,
                "max_loss": 0.21,
                "rr_actual": 1.38,
                "pmp": 0.35,
                "bid_ask_quality": "PASS",
                "dealer_gate_tier": "A",
                "dealer_weighted_score": 0.82,
                "wall_proximity_score": 0.7,
                "short_leg_bid": 0.08,
                "long_leg_ask": 0.29,
            },
            {
                "run_id": "2026-06-23-manual-091340",
                "expression_id": "IBIT:alt-narrow",
                "symbol": "IBIT",
                "expiration": "2026-06-26",
                "structure": "BULL_CALL_SPREAD",
                "expression_status": SpreadExpressionStatus.ALTERNATE.value,
                "long_strike": 36.5,
                "short_strike": 37.5,
                "width": 1.0,
                "debit": 0.28,
                "max_profit": 0.72,
                "max_loss": 0.28,
                "rr_actual": 2.57,
                "pmp": 0.32,
                "bid_ask_quality": "PASS",
                "dealer_gate_tier": "B",
                "dealer_weighted_score": 0.65,
                "wall_proximity_score": 0.55,
                "short_leg_bid": 0.05,
                "long_leg_ask": 0.33,
            },
        ]
    )


def test_ibit_primary_not_claimed_best() -> None:
    frontier = build_expression_frontier(
        _ibit_run_expressions(), run_id="2026-06-23-manual-091340"
    )
    ibit = next(s for s in frontier.symbol_summaries if s.symbol == "IBIT")
    note = ibit.frontier_comparison_note.lower()
    assert "valid but not proven optimal" in note
    assert "operator frontier review required" in note
    assert "compare" in note and "wider" in note
    assert ibit.operator_challenge_flag is True
    assert "primary_narrow_wider_valid_spreads_exist" in ibit.operator_challenge_reason


def test_manual_frontier_absent_flags_challenge(tmp_path: Path) -> None:
    advisory_dir = tmp_path / "data/advisory"
    advisory_dir.mkdir(parents=True)
    manual = {
        "expressions": [
            {
                "symbol": "IBIT",
                "expiration": "2026-06-26",
                "structure": "BULL_CALL_SPREAD",
                "long_strike": 36.5,
                "short_strike": 39.0,
                "reward_risk": 5.5,
            }
        ]
    }
    manual_frontier_path(tmp_path, "run-1").write_text(json.dumps(manual), encoding="utf-8")

    frontier = build_expression_frontier(
        _ibit_run_expressions(),
        base_dir=tmp_path,
        run_id="run-1",
    )
    ibit = next(s for s in frontier.symbol_summaries if s.symbol == "IBIT")
    assert ibit.operator_challenge_flag is True
    assert "manual_frontier_expression_absent_from_scan" in ibit.operator_challenge_reason
    assert "frontier candidate" in ibit.frontier_comparison_note.lower()


def test_frontier_columns_on_expression_rows() -> None:
    frontier = build_expression_frontier(_ibit_run_expressions())
    primary = next(r for r in frontier.expression_rows if r.get("expression_id") == "IBIT:primary")
    assert primary["frontier_role"] == "PRIMARY_SELECTED"
    assert primary["dealer_rank"] == 1
    assert primary["operator_challenge_flag"] is True
    assert primary["frontier_comparison_note"]


def test_frontier_paper_gate_withholds_approved_symbol() -> None:
    frontier = build_expression_frontier(_ibit_run_expressions())
    audit = pd.DataFrame(
        [
            {
                "symbol": "IBIT",
                "paper_approval_status": "APPROVED_FOR_PAPER_REVIEW",
                "classification": "APPROVED_PAPER",
                "reject_reason": "",
            }
        ]
    )
    out = apply_frontier_paper_gate_to_audit(audit, frontier)
    assert out.iloc[0]["reject_reason"] == PAPER_GATE_FRONTIER_REVIEW


def test_run_advisory_includes_frontier_payload(tmp_path: Path) -> None:
    run_id = "2026-06-23-manual-091340"
    expr_path = tmp_path / "data/processed" / f"{run_id}_alpaca_hydration_expressions.csv"
    expr_path.parent.mkdir(parents=True)
    _ibit_run_expressions().to_csv(expr_path, index=False)
    context_path = tmp_path / "data/processed/context" / f"{run_id}_context.csv"
    context_path.parent.mkdir(parents=True)
    pd.DataFrame([{"symbol": "IBIT", "notes": "current_price=36.2"}]).to_csv(context_path, index=False)
    candidates_path = tmp_path / "data/processed/candidates" / f"{run_id}_candidates.csv"
    candidates_path.parent.mkdir(parents=True)
    pd.DataFrame([{"symbol": "IBIT"}]).to_csv(candidates_path, index=False)
    risk_path = tmp_path / "data/processed/risk" / f"{run_id}_risk_audit.csv"
    risk_path.parent.mkdir(parents=True)
    pd.DataFrame([{"symbol": "IBIT", "classification": "ALTERNATES_AVAILABLE"}]).to_csv(
        risk_path, index=False
    )

    manifest = OrbRunManifest(
        run_id=run_id,
        run_date="2026-06-23",
        run_ts=pd.Timestamp("2026-06-23T09:13:40"),
        mode="manual",
        context_artifact=str(context_path),
        candidates_artifact=str(candidates_path),
        expressions_artifact=str(expr_path),
        risk_audit_artifact=str(risk_path),
    )
    result = build_run_advisory(tmp_path, manifest)
    assert result.run_advisory["frontier_review_required_before_paper"] is True
    summaries = result.run_advisory["expression_frontier_summaries"]
    assert isinstance(summaries, list) and summaries
    ibit = next(s for s in summaries if s["symbol"] == "IBIT")
    assert "not proven optimal" in ibit["frontier_comparison_note"]
