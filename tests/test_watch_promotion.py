"""WATCH expression operator promotion gate (dry-run; no submit)."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from qops.risk.watch_promotion_review import evaluate_watch_promotion, run_watch_promotion_review
from qops.schemas.candidate_loop import (
    CandidateLoopStatus,
    PaperRouteStatus,
    SpreadExpressionStatus,
)


def _watch_expression_row() -> pd.Series:
    return pd.Series(
        {
            "run_id": "2026-06-22-manual-test",
            "expression_id": "NIO:BULL_CALL_SPREAD:leg1:leg2",
            "candidate_id": "NIO:2026-06-22",
            "symbol": "NIO",
            "trade_date": "2026-06-22",
            "structure": "BULL_CALL_SPREAD",
            "expression_status": SpreadExpressionStatus.WATCH.value,
            "dealer_gate_tier": "C",
            "dealer_weighted_score": 7,
            "rr_actual": 1.30,
            "rr_dealer_required": 1.25,
            "pmp": 0.45,
            "pmp_dealer_max": 0.48,
            "max_loss": 250.0,
            "debit": 2.5,
            "width": 5.0,
            "quote_age_seconds": 45,
        }
    )


def _candidate_row() -> pd.Series:
    return pd.Series(
        {
            "symbol": "NIO",
            "trade_date": "2026-06-22",
            "source_profile": "reverse_vrp",
            "current_price": 4.0,
            "call_wall": 4.5,
            "put_wall": 3.5,
            "one_month_iv": 0.5,
            "one_month_rv": 0.55,
        }
    )


def test_watch_expression_requires_operator_reason() -> None:
    result = evaluate_watch_promotion(
        run_id="2026-06-22-manual-test",
        expression_row=_watch_expression_row(),
        candidate_row=_candidate_row(),
        operator_decision="approve",
        operator_reason="",
        live_mode_enabled=False,
        broker_mutation_occurred=False,
    )
    assert result.promotion_status == "BLOCKED_MISSING_REASON"
    assert "missing_operator_reason" in result.promotion_block_reason


def test_watch_expression_promotion_does_not_submit() -> None:
    with patch("qops.execution.alpaca_paper_bridge.submit_alpaca_paper_mleg_order") as submit:
        evaluate_watch_promotion(
            run_id="2026-06-22-manual-test",
            expression_row=_watch_expression_row(),
            candidate_row=_candidate_row(),
            operator_decision="approve",
            operator_reason="operator confirms wall alignment",
            live_mode_enabled=False,
            broker_mutation_occurred=False,
        )
    submit.assert_not_called()


def test_watch_expression_promotion_blocks_live_mode() -> None:
    result = evaluate_watch_promotion(
        run_id="2026-06-22-manual-test",
        expression_row=_watch_expression_row(),
        candidate_row=_candidate_row(),
        operator_decision="approve",
        operator_reason="reviewed",
        live_mode_enabled=True,
        broker_mutation_occurred=False,
    )
    assert result.promotion_status == "BLOCKED_LIVE_MODE"


def test_watch_expression_promotion_sets_paper_review_ready() -> None:
    result = evaluate_watch_promotion(
        run_id="2026-06-22-manual-test",
        expression_row=_watch_expression_row(),
        candidate_row=_candidate_row(),
        operator_decision="approve",
        operator_reason="operator confirms economics",
        live_mode_enabled=False,
        broker_mutation_occurred=False,
    )
    assert result.promotion_status == "WATCH_OPERATOR_APPROVED"
    assert result.paper_route_status == PaperRouteStatus.PAPER_REVIEW_READY.value
    assert result.expression_status == SpreadExpressionStatus.OPERATOR_APPROVED_WATCH.value
    assert result.candidate_loop_status == CandidateLoopStatus.WATCH_OPERATOR_APPROVED.value


def test_watch_expression_promotion_respects_risk_cap() -> None:
    row = _watch_expression_row()
    row = row.copy()
    row["max_loss"] = 900.0
    result = evaluate_watch_promotion(
        run_id="2026-06-22-manual-test",
        expression_row=row,
        candidate_row=_candidate_row(),
        operator_decision="approve",
        operator_reason="should block",
        live_mode_enabled=False,
        broker_mutation_occurred=False,
    )
    assert result.promotion_status == "BLOCKED_RISK_CAP"


def test_watch_expression_promotion_blocks_non_watch_expression() -> None:
    row = _watch_expression_row()
    row = row.copy()
    row["expression_status"] = SpreadExpressionStatus.PRIMARY.value
    result = evaluate_watch_promotion(
        run_id="2026-06-22-manual-test",
        expression_row=row,
        candidate_row=_candidate_row(),
        operator_decision="approve",
        operator_reason="invalid",
        live_mode_enabled=False,
        broker_mutation_occurred=False,
    )
    assert "not_watch_expression" in result.promotion_block_reason


def test_watch_expression_promotion_loads_expression(tmp_path) -> None:
    expr_path = tmp_path / "expressions.csv"
    cand_path = tmp_path / "candidates.csv"
    df = pd.DataFrame([_watch_expression_row().to_dict()])
    df.to_csv(expr_path, index=False)
    pd.DataFrame([_candidate_row().to_dict()]).to_csv(cand_path, index=False)
    result = run_watch_promotion_review(
        base_dir=tmp_path,
        run_id="2026-06-22-manual-test",
        run_date="2026-06-22",
        expression_id="NIO:BULL_CALL_SPREAD:leg1:leg2",
        operator_decision="approve",
        operator_reason="ok",
        live_mode_enabled=False,
        broker_mutation_occurred=False,
        expressions_path=expr_path,
        candidates_path=cand_path,
        dry_run=True,
    )
    assert result.promotion_status == "WATCH_OPERATOR_APPROVED"
