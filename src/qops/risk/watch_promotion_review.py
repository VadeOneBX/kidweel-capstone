"""Operator-only WATCH expression promotion (dry-run review; no paper submit)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import pandas as pd

from qops.risk.paper_approval import DEFAULT_MAX_RISK_PER_CANDIDATE
from qops.schemas.candidate_loop import (
    CandidateLoopStatus,
    PaperRouteStatus,
    SpreadExpressionStatus,
)

WATCH_PROMOTION_CSV_COLUMNS = (
    "run_id",
    "review_timestamp_utc",
    "operator_decision",
    "operator_reason",
    "candidate_id",
    "expression_id",
    "symbol",
    "structure",
    "dealer_gate_tier",
    "dealer_weighted_score",
    "rr_actual",
    "rr_dealer_required",
    "pmp",
    "pmp_dealer_max",
    "max_loss",
    "quote_age_seconds",
    "promotion_status",
    "promotion_block_reason",
    "paper_route_status",
    "broker_mutation_occurred",
)

RR_OPERATOR_TOLERANCE = 0.10
PMP_OPERATOR_TOLERANCE = 0.03
MAX_QUOTE_AGE_SECONDS = 300.0

OperatorDecision = Literal["approve", "reject"]


@dataclass(frozen=True, slots=True)
class WatchPromotionReviewResult:
    promotion_status: str
    promotion_block_reason: str
    paper_route_status: str
    expression_status: str
    candidate_loop_status: str
    broker_mutation_occurred: bool
    review_row: dict[str, object]


def watch_promotion_artifact_path(base_dir: Path, run_id: str) -> Path:
    return base_dir / "data" / "processed" / "runs" / run_id / "watch_promotion_review.csv"


def _parse_float(raw: object) -> float | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    if isinstance(raw, str) and not raw.strip():
        return None
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    return val if math.isfinite(val) else None


def _candidate_row_for_expression(
    candidates_df: pd.DataFrame,
    expression_row: pd.Series,
) -> pd.Series | None:
    if candidates_df.empty:
        return None
    cid = str(expression_row.get("candidate_id", "")).strip()
    sym = str(expression_row.get("symbol", "")).strip().upper()
    td = str(expression_row.get("trade_date", "")).strip()
    if cid and "candidate_id" in candidates_df.columns:
        hits = candidates_df[candidates_df["candidate_id"].astype(str) == cid]
        if not hits.empty:
            return hits.iloc[0]
    if sym and td and {"symbol", "trade_date"}.issubset(candidates_df.columns):
        hits = candidates_df[
            (candidates_df["symbol"].astype(str).str.upper() == sym)
            & (candidates_df["trade_date"].astype(str) == td)
        ]
        if not hits.empty:
            return hits.iloc[0]
    if sym and "symbol" in candidates_df.columns:
        hits = candidates_df[candidates_df["symbol"].astype(str).str.upper() == sym]
        if not hits.empty:
            return hits.iloc[0]
    return None


def evaluate_watch_promotion(
    *,
    run_id: str,
    expression_row: pd.Series,
    candidate_row: pd.Series | None,
    operator_decision: OperatorDecision,
    operator_reason: str,
    live_mode_enabled: bool,
    broker_mutation_occurred: bool,
    max_risk_per_candidate: float = DEFAULT_MAX_RISK_PER_CANDIDATE,
) -> WatchPromotionReviewResult:
    block_reasons: list[str] = []
    expr_status = str(expression_row.get("expression_status", "")).strip()
    if expr_status != SpreadExpressionStatus.WATCH.value:
        block_reasons.append("not_watch_expression")

    if not operator_reason.strip():
        block_reasons.append("missing_operator_reason")

    if live_mode_enabled:
        return _blocked(
            run_id=run_id,
            expression_row=expression_row,
            candidate_row=candidate_row,
            operator_decision=operator_decision,
            operator_reason=operator_reason,
            promotion_status="BLOCKED_LIVE_MODE",
            block_reasons=block_reasons or ["live_mode_enabled"],
            broker_mutation_occurred=broker_mutation_occurred,
        )

    if broker_mutation_occurred:
        block_reasons.append("broker_mutation_at_review")

    ctx = candidate_row if candidate_row is not None else expression_row
    source_profile = str(ctx.get("source_profile", "")).strip()
    if not source_profile:
        block_reasons.append("missing_source_profile")

    current_price = _parse_float(ctx.get("current_price"))
    if current_price is None or current_price <= 0:
        block_reasons.append("missing_current_price")

    call_wall = _parse_float(ctx.get("call_wall"))
    put_wall = _parse_float(ctx.get("put_wall"))
    if call_wall is None and put_wall is None:
        block_reasons.append("missing_call_or_put_wall")

    profile = source_profile.lower()
    one_month_iv = _parse_float(ctx.get("one_month_iv"))
    one_month_rv = _parse_float(ctx.get("one_month_rv"))
    if profile == "reverse_vrp" and (one_month_iv is None or one_month_rv is None):
        block_reasons.append("missing_one_month_iv_or_rv")

    tier = str(expression_row.get("dealer_gate_tier", "")).strip().upper()
    if tier not in {"C", "D"}:
        block_reasons.append("dealer_gate_tier_not_c_or_d")

    max_loss = _parse_float(expression_row.get("max_loss"))
    if max_loss is None or max_loss <= 0:
        block_reasons.append("invalid_max_loss")
    elif max_loss > max_risk_per_candidate:
        return _blocked(
            run_id=run_id,
            expression_row=expression_row,
            candidate_row=candidate_row,
            operator_decision=operator_decision,
            operator_reason=operator_reason,
            promotion_status="BLOCKED_RISK_CAP",
            block_reasons=block_reasons or ["max_loss_exceeds_cap"],
            broker_mutation_occurred=broker_mutation_occurred,
        )

    debit = _parse_float(expression_row.get("debit"))
    width = _parse_float(expression_row.get("width"))
    if debit is not None and debit <= 0:
        block_reasons.append("invalid_debit")
    if width is not None and width <= 0:
        block_reasons.append("invalid_width")

    rr_actual = _parse_float(expression_row.get("rr_actual"))
    rr_required = _parse_float(expression_row.get("rr_dealer_required"))
    if rr_actual is None or rr_required is None:
        block_reasons.append("missing_rr_fields")
    elif rr_actual < rr_required - RR_OPERATOR_TOLERANCE:
        block_reasons.append("rr_below_tier_tolerance")

    pmp = _parse_float(expression_row.get("pmp"))
    pmp_max = _parse_float(expression_row.get("pmp_dealer_max"))
    if pmp is None or pmp_max is None:
        block_reasons.append("missing_pmp_fields")
    elif pmp > pmp_max + PMP_OPERATOR_TOLERANCE:
        block_reasons.append("pmp_above_tier_tolerance")

    quote_age_raw = expression_row.get("quote_age_seconds", "")
    quote_age = _parse_float(quote_age_raw)
    if quote_age is not None and quote_age > MAX_QUOTE_AGE_SECONDS:
        return _blocked(
            run_id=run_id,
            expression_row=expression_row,
            candidate_row=candidate_row,
            operator_decision=operator_decision,
            operator_reason=operator_reason,
            promotion_status="REQUOTE_REQUIRED",
            block_reasons=block_reasons or ["quote_age_stale"],
            broker_mutation_occurred=broker_mutation_occurred,
        )

    if operator_decision == "reject":
        return WatchPromotionReviewResult(
            promotion_status="WATCH_OPERATOR_REJECTED",
            promotion_block_reason="",
            paper_route_status=PaperRouteStatus.NOT_ROUTED.value,
            expression_status=SpreadExpressionStatus.OPERATOR_REJECTED_WATCH.value,
            candidate_loop_status=CandidateLoopStatus.WATCH_OPERATOR_REJECTED.value,
            broker_mutation_occurred=broker_mutation_occurred,
            review_row=_review_row(
                run_id=run_id,
                expression_row=expression_row,
                operator_decision=operator_decision,
                operator_reason=operator_reason,
                promotion_status="WATCH_OPERATOR_REJECTED",
                promotion_block_reason="",
                paper_route_status=PaperRouteStatus.NOT_ROUTED.value,
                broker_mutation_occurred=broker_mutation_occurred,
            ),
        )

    if block_reasons:
        status = "BLOCKED_MISSING_REASON" if "missing_operator_reason" in block_reasons else "BLOCKED"
        return _blocked(
            run_id=run_id,
            expression_row=expression_row,
            candidate_row=candidate_row,
            operator_decision=operator_decision,
            operator_reason=operator_reason,
            promotion_status=status,
            block_reasons=block_reasons,
            broker_mutation_occurred=broker_mutation_occurred,
        )

    return WatchPromotionReviewResult(
        promotion_status="WATCH_OPERATOR_APPROVED",
        promotion_block_reason="",
        paper_route_status=PaperRouteStatus.PAPER_REVIEW_READY.value,
        expression_status=SpreadExpressionStatus.OPERATOR_APPROVED_WATCH.value,
        candidate_loop_status=CandidateLoopStatus.WATCH_OPERATOR_APPROVED.value,
        broker_mutation_occurred=broker_mutation_occurred,
        review_row=_review_row(
            run_id=run_id,
            expression_row=expression_row,
            operator_decision=operator_decision,
            operator_reason=operator_reason,
            promotion_status="WATCH_OPERATOR_APPROVED",
            promotion_block_reason="",
            paper_route_status=PaperRouteStatus.PAPER_REVIEW_READY.value,
            broker_mutation_occurred=broker_mutation_occurred,
        ),
    )


def _blocked(
    *,
    run_id: str,
    expression_row: pd.Series,
    candidate_row: pd.Series | None,
    operator_decision: OperatorDecision,
    operator_reason: str,
    promotion_status: str,
    block_reasons: list[str],
    broker_mutation_occurred: bool,
) -> WatchPromotionReviewResult:
    reason = ";".join(block_reasons)
    return WatchPromotionReviewResult(
        promotion_status=promotion_status,
        promotion_block_reason=reason,
        paper_route_status=PaperRouteStatus.NOT_ROUTED.value,
        expression_status=str(expression_row.get("expression_status", SpreadExpressionStatus.WATCH.value)),
        candidate_loop_status=CandidateLoopStatus.WATCH_OPERATOR_REVIEW.value,
        broker_mutation_occurred=broker_mutation_occurred,
        review_row=_review_row(
            run_id=run_id,
            expression_row=expression_row,
            operator_decision=operator_decision,
            operator_reason=operator_reason,
            promotion_status=promotion_status,
            promotion_block_reason=reason,
            paper_route_status=PaperRouteStatus.NOT_ROUTED.value,
            broker_mutation_occurred=broker_mutation_occurred,
        ),
    )


def _review_row(
    *,
    run_id: str,
    expression_row: pd.Series,
    operator_decision: str,
    operator_reason: str,
    promotion_status: str,
    promotion_block_reason: str,
    paper_route_status: str,
    broker_mutation_occurred: bool,
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "review_timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "operator_decision": operator_decision,
        "operator_reason": operator_reason,
        "candidate_id": expression_row.get("candidate_id", ""),
        "expression_id": expression_row.get("expression_id", ""),
        "symbol": expression_row.get("symbol", ""),
        "structure": expression_row.get("structure", ""),
        "dealer_gate_tier": expression_row.get("dealer_gate_tier", ""),
        "dealer_weighted_score": expression_row.get("dealer_weighted_score", ""),
        "rr_actual": expression_row.get("rr_actual", ""),
        "rr_dealer_required": expression_row.get("rr_dealer_required", ""),
        "pmp": expression_row.get("pmp", ""),
        "pmp_dealer_max": expression_row.get("pmp_dealer_max", ""),
        "max_loss": expression_row.get("max_loss", ""),
        "quote_age_seconds": expression_row.get("quote_age_seconds", ""),
        "promotion_status": promotion_status,
        "promotion_block_reason": promotion_block_reason,
        "paper_route_status": paper_route_status,
        "broker_mutation_occurred": broker_mutation_occurred,
    }


def append_watch_promotion_review(
    base_dir: Path,
    run_id: str,
    review_row: dict[str, object],
) -> Path:
    path = watch_promotion_artifact_path(base_dir, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    row_df = pd.DataFrame([review_row], columns=list(WATCH_PROMOTION_CSV_COLUMNS))
    if path.is_file():
        existing = pd.read_csv(path)
        combined = pd.concat([existing, row_df], ignore_index=True)
        combined.to_csv(path, index=False)
    else:
        row_df.to_csv(path, index=False)
    return path


def load_expression_for_review(
    expressions_path: Path,
    *,
    run_id: str,
    expression_id: str,
) -> pd.Series:
    df = pd.read_csv(expressions_path)
    if "run_id" in df.columns:
        df = df[df["run_id"].astype(str) == str(run_id)]
    hits = df[df["expression_id"].astype(str) == str(expression_id)]
    if hits.empty:
        raise ValueError(f"expression_not_found:{expression_id}")
    return hits.iloc[0]


def run_watch_promotion_review(
    *,
    base_dir: Path,
    run_id: str,
    run_date: str,
    expression_id: str,
    operator_decision: OperatorDecision,
    operator_reason: str,
    live_mode_enabled: bool,
    broker_mutation_occurred: bool,
    expressions_path: Path | None = None,
    candidates_path: Path | None = None,
    dry_run: bool = True,
) -> WatchPromotionReviewResult:
    from qops.pipeline.alpaca_hydration_loop import expressions_artifact_path

    expr_path = expressions_path or expressions_artifact_path(base_dir, run_id)
    expression_row = load_expression_for_review(expr_path, run_id=run_id, expression_id=expression_id)

    candidate_row: pd.Series | None = None
    if candidates_path is not None and candidates_path.is_file():
        candidate_row = _candidate_row_for_expression(pd.read_csv(candidates_path), expression_row)

    result = evaluate_watch_promotion(
        run_id=run_id,
        expression_row=expression_row,
        candidate_row=candidate_row,
        operator_decision=operator_decision,
        operator_reason=operator_reason,
        live_mode_enabled=live_mode_enabled,
        broker_mutation_occurred=broker_mutation_occurred,
    )
    if not dry_run:
        append_watch_promotion_review(base_dir, run_id, result.review_row)
    return result
