"""STRUCT-C2A: Alpaca read-only hydration and spread expression selection for SG candidates."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from qops.backtest.alpaca_greeks_layer import (
    AlpacaGreeksCandidateRow,
    PaperLiveSymbolSpec,
    PAPER_LIVE_PROVENANCE,
    preflight_hydration_auth,
    stage_greeks_paper_live,
    try_create_option_client,
)
from qops.config.paper_live_params import REPO_PAPER_LIVE_DEFAULTS
from qops.risk.pmp_policy import min_rr_for_pmp
from qops.schemas.candidate_loop import CandidateLoopStatus, HydrationStatus, SpreadExpressionStatus
from qops.schemas.playbook import AllowedPlaybook
from qops.signals.classifier import compute_wall_distance_pct
from qops.strategy.dealer_expression_tier import (
    compute_dealer_weighted_score,
    dealer_tier_for_score,
    expression_passes_dealer_tier,
    resolve_dealer_direction_score,
    structure_direction,
)
from qops.strategy.spread_candidate_generator import (
    GeneratedSpreadCandidate,
    generate_spread_candidates,
    quote_rows_from_greeks_candidates,
)

PROVENANCE_TAG = "struct_c2a_alpaca_hydration_loop"

EXPRESSIONS_ARTIFACT_SUFFIX = "alpaca_hydration_expressions.csv"
# Legacy global filename (prefer run-keyed path via expressions_artifact_path).
EXPRESSIONS_ARTIFACT_NAME = EXPRESSIONS_ARTIFACT_SUFFIX


def expressions_artifact_path(base_dir: Path, run_id: str) -> Path:
    return base_dir / "data" / "processed" / f"{run_id}_{EXPRESSIONS_ARTIFACT_SUFFIX}"

DEBIT_STRUCTURE_FILTER = [
    AllowedPlaybook.BULL_CALL_SPREAD.value,
    AllowedPlaybook.BEAR_PUT_SPREAD.value,
]

C2A_EVIDENCE_COLUMNS = (
    "context_gate_status",
    "context_gate_reason",
    "candidate_loop_status",
    "hydration_status",
    "expression_count",
    "primary_expression_id",
    "watch_expression_id",
    "alternate_expression_count",
    "dealer_weighted_score",
    "dealer_gate_tier",
    "rr_baseline_required",
    "rr_dealer_required",
    "pmp_baseline_max",
    "pmp_dealer_max",
    "selection_reason",
    "data_gap_reason",
)

EXPRESSION_ARTIFACT_COLUMNS = (
    "run_id",
    "expression_id",
    "candidate_id",
    "symbol",
    "trade_date",
    "structure",
    "direction",
    "expiration",
    "dte",
    "long_leg_symbol",
    "short_leg_symbol",
    "long_strike",
    "short_strike",
    "width",
    "debit",
    "max_profit",
    "max_loss",
    "rr_actual",
    "pmp",
    "breakeven",
    "bid_ask_quality",
    "quote_age_seconds",
    "liquidity_score",
    "wall_target",
    "wall_type",
    "wall_distance_pct",
    "short_strike_wall_distance_pct",
    "cheap_iv_score",
    "wall_proximity_score",
    "dealer_direction_score",
    "dealer_direction_score_source",
    "dealer_direction_score_status",
    "dealer_direction_score_reason",
    "spread_efficiency_score",
    "dealer_weighted_score",
    "dealer_gate_tier",
    "rr_baseline_required",
    "rr_dealer_required",
    "pmp_baseline_max",
    "pmp_dealer_max",
    "expression_status",
    "expression_reason",
    "selection_rank",
)

StageGreeksFn = Callable[
    ...,
    tuple[list[AlpacaGreeksCandidateRow], bool, Any, list[Any]],
]
CreateClientFn = Callable[[], tuple[Any | None, str | None]]


def _expression_id(expr: GeneratedSpreadCandidate) -> str:
    return (
        f"{expr.underlying_symbol}:{expr.structure_type}:"
        f"{expr.long_option_symbol}:{expr.short_option_symbol}"
    )


def _candidate_id(row: dict[str, object]) -> str:
    sym = str(row.get("symbol", "")).strip().upper()
    td = str(row.get("trade_date", "")).strip()
    return f"{sym}:{td}" if sym and td else sym or td


def _short_strike(expr: GeneratedSpreadCandidate) -> float:
    if expr.structure_type == AllowedPlaybook.BULL_CALL_SPREAD.value:
        return expr.reference_strike + expr.spread_width
    if expr.structure_type == AllowedPlaybook.BEAR_PUT_SPREAD.value:
        return expr.reference_strike - expr.spread_width
    return expr.reference_strike


def _wall_alignment(
    expr: GeneratedSpreadCandidate,
    *,
    current_price: float | None,
    call_wall: float | None,
    put_wall: float | None,
) -> tuple[float | None, str, float | None, float | None]:
    if current_price is None or current_price <= 0:
        return None, "", None, None
    short = _short_strike(expr)
    if expr.structure_type == AllowedPlaybook.BULL_CALL_SPREAD.value and call_wall is not None:
        dist = compute_wall_distance_pct(short, call_wall)
        return call_wall, "call_wall", dist, dist
    if expr.structure_type == AllowedPlaybook.BEAR_PUT_SPREAD.value and put_wall is not None:
        dist = compute_wall_distance_pct(short, put_wall)
        return put_wall, "put_wall", dist, dist
    return None, "", None, None


def _float_or_none(raw: object) -> float | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    return val if math.isfinite(val) else None


def _core_expression_viable(expr: GeneratedSpreadCandidate) -> bool:
    if expr.spread_width <= 0 or expr.net_debit_or_credit <= 0:
        return False
    if expr.pmp_for_gate is None:
        return False
    if not math.isfinite(expr.math.reward_risk) or expr.math.reward_risk <= 0:
        return False
    return expr.math.max_loss > 0


def _liquidity_score(expr: GeneratedSpreadCandidate) -> float:
    if expr.math.passes_spread_math_gate and expr.candidate_pass:
        return 1.0
    if expr.math.passes_spread_math_gate:
        return 0.75
    return 0.25


def _bid_ask_quality(expr: GeneratedSpreadCandidate) -> str:
    if expr.math.passes_spread_math_gate:
        return "PASS"
    if expr.pmp_for_gate is not None and expr.math.max_loss > 0:
        return "WATCH"
    return "FAIL"


def _rank_key(
    *,
    passes_tier: bool,
    dealer_score: int,
    pmp: float | None,
    debit_width: float,
    liquidity: float,
    wall_score: int,
    max_loss: float,
    bid_ask: str,
) -> tuple:
    bid_penalty = 0 if bid_ask == "PASS" else 1 if bid_ask == "WATCH" else 2
    pmp_sort = pmp if pmp is not None else 1.0
    return (
        1 if passes_tier else 0,
        dealer_score,
        -pmp_sort,
        -debit_width if debit_width > 0 else 0.0,
        liquidity,
        wall_score,
        -max_loss,
        -bid_penalty,
    )


def _baseline_rr_required(pmp: float | None) -> float | None:
    if pmp is None:
        return None
    try:
        return min_rr_for_pmp(pmp)
    except ValueError:
        return None


def _score_expression(
    expr: GeneratedSpreadCandidate,
    *,
    candidate_row: dict[str, object],
) -> dict[str, object]:
    current_price = _float_or_none(candidate_row.get("current_price"))
    call_wall = _float_or_none(candidate_row.get("call_wall"))
    put_wall = _float_or_none(candidate_row.get("put_wall"))
    iv_rank = _float_or_none(candidate_row.get("iv_rank"))
    gamma = _float_or_none(candidate_row.get("gamma_ratio"))
    source_profile = str(candidate_row.get("source_profile", "") or "")

    wall_target, wall_type, wall_dist, short_wall_dist = _wall_alignment(
        expr,
        current_price=current_price,
        call_wall=call_wall,
        put_wall=put_wall,
    )
    short_strike_val = _short_strike(expr)
    direction_resolution = resolve_dealer_direction_score(
        source_profile=source_profile,
        gamma_ratio=gamma,
        candidate_row=candidate_row,
        structure=expr.structure_type,
        short_strike=short_strike_val,
    )
    debit = float(expr.net_debit_or_credit)
    total, wall_sc, cheap_sc, dir_sc, eff_sc = compute_dealer_weighted_score(
        short_strike_wall_distance_pct=short_wall_dist,
        iv_rank=iv_rank,
        gamma_ratio=gamma,
        net_debit=debit,
        spread_width=expr.spread_width,
        resolved_direction_score=direction_resolution.score,
    )
    gate = dealer_tier_for_score(total)
    pmp = expr.pmp_for_gate
    rr = expr.math.reward_risk
    passes_tier = expression_passes_dealer_tier(
        reward_risk=rr,
        pmp=pmp,
        gate=gate,
    )
    rr_base = _baseline_rr_required(pmp)
    width = expr.spread_width
    debit_width = (width - debit) / width if width > 0 else 0.0
    liquidity = _liquidity_score(expr)
    bid_ask = _bid_ask_quality(expr)
    rank_key = _rank_key(
        passes_tier=passes_tier,
        dealer_score=total,
        pmp=pmp,
        debit_width=debit_width,
        liquidity=liquidity,
        wall_score=wall_sc,
        max_loss=expr.math.max_loss,
        bid_ask=bid_ask,
    )
    return {
        "expr": expr,
        "rank_key": rank_key,
        "passes_tier": passes_tier,
        "dealer_weighted_score": total,
        "wall_proximity_score": wall_sc,
        "cheap_iv_score": cheap_sc,
        "dealer_direction_score": dir_sc,
        "dealer_direction_score_source": direction_resolution.source,
        "dealer_direction_score_status": direction_resolution.status,
        "dealer_direction_score_reason": direction_resolution.reason,
        "spread_efficiency_score": eff_sc,
        "dealer_gate_tier": gate.tier,
        "rr_baseline_required": rr_base,
        "rr_dealer_required": gate.rr_dealer_required,
        "pmp_baseline_max": pmp,
        "pmp_dealer_max": gate.pmp_dealer_max,
        "wall_target": wall_target if wall_target is not None else "",
        "wall_type": wall_type,
        "wall_distance_pct": wall_dist if wall_dist is not None else "",
        "short_strike_wall_distance_pct": short_wall_dist if short_wall_dist is not None else "",
        "liquidity_score": liquidity,
        "bid_ask_quality": bid_ask,
        "quote_age_seconds": "",
    }


def _label_expression_status(
    *,
    selection_rank: int,
    passes_tier: bool,
    viable: bool,
) -> tuple[str, str]:
    if not viable:
        return (
            SpreadExpressionStatus.FAILED_EXPRESSION.value,
            "expression economics incomplete or missing PMP",
        )
    if selection_rank == 1:
        if passes_tier:
            return SpreadExpressionStatus.PRIMARY.value, "primary expression under dealer-weighted tier"
        return (
            SpreadExpressionStatus.WATCH.value,
            "Expression not selected under current dealer-weighted tier",
        )
    if passes_tier:
        return SpreadExpressionStatus.ALTERNATE.value, "Alternate expression retained"
    return (
        SpreadExpressionStatus.WATCH.value,
        "Expression not selected under current dealer-weighted tier",
    )


def rank_expressions_for_candidate(
    expressions: list[GeneratedSpreadCandidate],
    *,
    candidate_row: dict[str, object],
) -> list[dict[str, object]]:
    """Score, rank, and label spread expressions for one SpotGamma candidate row."""
    scored = [_score_expression(e, candidate_row=candidate_row) for e in expressions]
    viable = [s for s in scored if _core_expression_viable(s["expr"])]  # type: ignore[arg-type]
    failed = [s for s in scored if not _core_expression_viable(s["expr"])]  # type: ignore[arg-type]

    ordered = sorted(viable, key=lambda s: s["rank_key"], reverse=True)  # type: ignore[arg-type]
    records: list[dict[str, object]] = []
    rank = 0
    for item in ordered:
        rank += 1
        expr: GeneratedSpreadCandidate = item["expr"]  # type: ignore[assignment]
        status, reason = _label_expression_status(
            selection_rank=rank,
            passes_tier=bool(item["passes_tier"]),
            viable=True,
        )
        records.append(_expression_record(expr, candidate_row, item, status, reason, rank))

    fail_rank = rank
    for item in failed:
        fail_rank += 1
        expr = item["expr"]  # type: ignore[assignment]
        status, reason = _label_expression_status(
            selection_rank=fail_rank,
            passes_tier=False,
            viable=False,
        )
        records.append(_expression_record(expr, candidate_row, item, status, reason, fail_rank))
    return records


def _expression_record(
    expr: GeneratedSpreadCandidate,
    candidate_row: dict[str, object],
    scored: dict[str, object],
    expression_status: str,
    expression_reason: str,
    selection_rank: int,
) -> dict[str, object]:
    trade_date = str(candidate_row.get("trade_date", expr.trade_date))
    dte = max(0, (pd.Timestamp(expr.expiration) - pd.Timestamp(trade_date)).days)
    short_strike = _short_strike(expr)
    debit = expr.net_debit_or_credit if expr.net_debit_or_credit > 0 else ""
    return {
        "run_id": str(candidate_row.get("run_id", "") or ""),
        "expression_id": _expression_id(expr),
        "candidate_id": _candidate_id(candidate_row),
        "symbol": expr.underlying_symbol,
        "trade_date": trade_date,
        "structure": expr.structure_type,
        "direction": structure_direction(expr.structure_type),
        "expiration": expr.expiration,
        "dte": dte,
        "long_leg_symbol": expr.long_option_symbol,
        "short_leg_symbol": expr.short_option_symbol,
        "long_strike": expr.reference_strike,
        "short_strike": short_strike,
        "width": expr.spread_width,
        "debit": debit,
        "max_profit": expr.math.max_profit,
        "max_loss": expr.math.max_loss,
        "rr_actual": expr.math.reward_risk,
        "pmp": expr.pmp_for_gate,
        "breakeven": expr.math.break_even,
        "bid_ask_quality": scored["bid_ask_quality"],
        "quote_age_seconds": scored["quote_age_seconds"],
        "liquidity_score": scored["liquidity_score"],
        "wall_target": scored["wall_target"],
        "wall_type": scored["wall_type"],
        "wall_distance_pct": scored["wall_distance_pct"],
        "short_strike_wall_distance_pct": scored["short_strike_wall_distance_pct"],
        "cheap_iv_score": scored["cheap_iv_score"],
        "wall_proximity_score": scored["wall_proximity_score"],
        "dealer_direction_score": scored["dealer_direction_score"],
        "dealer_direction_score_source": scored.get("dealer_direction_score_source", ""),
        "dealer_direction_score_status": scored.get("dealer_direction_score_status", ""),
        "dealer_direction_score_reason": scored.get("dealer_direction_score_reason", ""),
        "spread_efficiency_score": scored["spread_efficiency_score"],
        "dealer_weighted_score": scored["dealer_weighted_score"],
        "dealer_gate_tier": scored["dealer_gate_tier"],
        "rr_baseline_required": scored["rr_baseline_required"],
        "rr_dealer_required": scored["rr_dealer_required"],
        "pmp_baseline_max": scored["pmp_baseline_max"],
        "pmp_dealer_max": scored["pmp_dealer_max"],
        "expression_status": expression_status,
        "expression_reason": expression_reason,
        "selection_rank": selection_rank,
    }


def expressions_to_dataframe(records: list[dict[str, object]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=list(EXPRESSION_ARTIFACT_COLUMNS))
    return pd.DataFrame(records)


def summarize_expression_artifact(df: pd.DataFrame) -> dict[str, int]:
    if df.empty or "expression_status" not in df.columns:
        return {
            "expression_count_total": 0,
            "primary_expression_count": 0,
            "alternate_expression_count": 0,
            "watch_expression_count": 0,
            "failed_expression_count": 0,
            "dealer_tier_a": 0,
            "dealer_tier_b": 0,
            "dealer_tier_c": 0,
            "dealer_tier_d": 0,
            "dealer_tier_e": 0,
        }
    status = df["expression_status"].astype(str)
    tier = df.get("dealer_gate_tier", pd.Series(dtype=str)).astype(str)
    return {
        "expression_count_total": len(df),
        "primary_expression_count": int((status == SpreadExpressionStatus.PRIMARY.value).sum()),
        "alternate_expression_count": int((status == SpreadExpressionStatus.ALTERNATE.value).sum()),
        "watch_expression_count": int((status == SpreadExpressionStatus.WATCH.value).sum()),
        "failed_expression_count": int((status == SpreadExpressionStatus.FAILED_EXPRESSION.value).sum()),
        "dealer_tier_a": int((tier == "A").sum()),
        "dealer_tier_b": int((tier == "B").sum()),
        "dealer_tier_c": int((tier == "C").sum()),
        "dealer_tier_d": int((tier == "D").sum()),
        "dealer_tier_e": int((tier == "E").sum()),
    }


def _pick_primary_from_records(
    records: list[dict[str, object]],
) -> tuple[dict[str, object] | None, list[dict[str, object]]]:
    if not records:
        return None, []
    primaries = [
        r
        for r in records
        if str(r.get("expression_status", "")) == SpreadExpressionStatus.PRIMARY.value
    ]
    if primaries:
        ordered = sorted(primaries, key=lambda r: int(r.get("selection_rank", 9999)))
        primary = ordered[0]
        alternates = [
            r
            for r in records
            if str(r.get("expression_status", ""))
            in {SpreadExpressionStatus.ALTERNATE.value, SpreadExpressionStatus.WATCH.value}
            and int(r.get("selection_rank", 9999)) > int(primary.get("selection_rank", 0))
        ]
        return primary, alternates

    watches = [
        r
        for r in records
        if str(r.get("expression_status", "")) == SpreadExpressionStatus.WATCH.value
    ]
    if watches:
        ordered = sorted(watches, key=lambda r: int(r.get("selection_rank", 9999)))
        return ordered[0], ordered[1:]
    return None, []


def _apply_primary_to_row(row: pd.Series, primary: dict[str, object]) -> dict[str, object]:
    debit = primary.get("debit", "")
    return {
        "structure": primary.get("structure", ""),
        "expiration": primary.get("expiration", ""),
        "dte": primary.get("dte", ""),
        "long_leg_symbol": primary.get("long_leg_symbol", ""),
        "short_leg_symbol": primary.get("short_leg_symbol", ""),
        "long_strike": primary.get("long_strike", ""),
        "short_strike": primary.get("short_strike", ""),
        "debit": debit,
        "credit": "",
        "width": primary.get("width", ""),
        "max_profit": primary.get("max_profit", ""),
        "max_loss": primary.get("max_loss", ""),
        "rr_actual": primary.get("rr_actual", ""),
        "pmp": primary.get("pmp", ""),
        "ev": "",
        "liquidity_status": "HYDRATED"
        if primary.get("expression_status") == SpreadExpressionStatus.PRIMARY.value
        else "WATCH",
    }


def _symbol_specs_from_candidates(df: pd.DataFrame, *, max_symbols: int) -> list[PaperLiveSymbolSpec]:
    if df.empty or "symbol" not in df.columns:
        return []
    seen: set[str] = set()
    specs: list[PaperLiveSymbolSpec] = []
    for _, row in df.iterrows():
        sym = str(row.get("symbol", "")).strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        price_raw = row.get("current_price")
        price: float | None = None
        if price_raw is not None and not (isinstance(price_raw, float) and pd.isna(price_raw)):
            try:
                val = float(price_raw)
                if val > 0:
                    price = val
            except (TypeError, ValueError):
                price = None
        specs.append(
            PaperLiveSymbolSpec(
                symbol=sym,
                current_price=price,
                source_profile=str(row.get("source_profile", "") or "sg_candidate"),
                has_spy_context=bool(row.get("has_spy_context")),
                provenance=f"{PAPER_LIVE_PROVENANCE}|{PROVENANCE_TAG}",
            )
        )
        if len(specs) >= max_symbols:
            break
    return specs


def _default_loop_fields() -> dict[str, object]:
    return {
        "context_gate_status": "",
        "context_gate_reason": "",
        "candidate_loop_status": CandidateLoopStatus.HYDRATION_PENDING.value,
        "hydration_status": HydrationStatus.REQUERY_REQUIRED.value,
        "expression_count": 0,
        "primary_expression_id": "",
        "watch_expression_id": "",
        "alternate_expression_count": 0,
        "dealer_weighted_score": "",
        "dealer_gate_tier": "",
        "rr_baseline_required": "",
        "rr_dealer_required": "",
        "pmp_baseline_max": "",
        "pmp_dealer_max": "",
        "selection_reason": "",
        "data_gap_reason": "",
    }


def _expressions_by_symbol(
    expressions: list[GeneratedSpreadCandidate],
) -> dict[str, list[GeneratedSpreadCandidate]]:
    grouped: dict[str, list[GeneratedSpreadCandidate]] = {}
    for expr in expressions:
        sym = expr.underlying_symbol.strip().upper()
        grouped.setdefault(sym, []).append(expr)
    return grouped


@dataclass(frozen=True, slots=True)
class AlpacaHydrationLoopResult:
    candidate_df: pd.DataFrame
    expressions_df: pd.DataFrame
    greeks_row_count: int
    expression_count: int
    fetch_attempted: bool
    fetch_skip_reason: str
    expressions_artifact: str


def run_alpaca_expression_hydration(
    df: pd.DataFrame,
    *,
    fetch: bool = True,
    max_symbols: int = 50,
    create_client_fn: CreateClientFn = try_create_option_client,
    stage_greeks_fn: StageGreeksFn = stage_greeks_paper_live,
    expressions_output_path: Path | str | None = None,
) -> AlpacaHydrationLoopResult:
    """
    Read-only Alpaca chain staging → spread expressions → dealer-weighted ranking.

    Never submits orders. Skips network when ``fetch=False`` or credentials are missing.
    """
    empty_expr = expressions_to_dataframe([])
    artifact_path = str(expressions_output_path or "")

    if df.empty:
        return AlpacaHydrationLoopResult(
            candidate_df=df,
            expressions_df=empty_expr,
            greeks_row_count=0,
            expression_count=0,
            fetch_attempted=False,
            fetch_skip_reason="empty_candidates",
            expressions_artifact=artifact_path,
        )

    out = df.copy()
    defaults = _default_loop_fields()
    for col in C2A_EVIDENCE_COLUMNS:
        if col not in out.columns:
            out[col] = defaults[col]
        else:
            empty_mask = out[col].isna() | (out[col].astype(str).str.strip() == "")
            if empty_mask.any():
                out.loc[empty_mask, col] = defaults[col]

    specs = _symbol_specs_from_candidates(out, max_symbols=max_symbols)
    if not specs:
        out["candidate_loop_status"] = CandidateLoopStatus.PARKED_DATA_GAP.value
        out["hydration_status"] = HydrationStatus.PARKED_DATA_GAP.value
        out["data_gap_reason"] = "missing_symbol_on_candidates"
        return AlpacaHydrationLoopResult(
            candidate_df=out,
            expressions_df=empty_expr,
            greeks_row_count=0,
            expression_count=0,
            fetch_attempted=False,
            fetch_skip_reason="missing_symbol_on_candidates",
            expressions_artifact=artifact_path,
        )

    greeks_rows: list[AlpacaGreeksCandidateRow] = []
    fetch_attempted = False
    skip_reason = ""

    if fetch:
        preflight_err = preflight_hydration_auth()
        if preflight_err:
            skip_reason = preflight_err
            out["candidate_loop_status"] = CandidateLoopStatus.PARKED_DATA_GAP.value
            out["hydration_status"] = HydrationStatus.PARKED_DATA_GAP.value
            out["data_gap_reason"] = skip_reason
            return AlpacaHydrationLoopResult(
                candidate_df=out,
                expressions_df=empty_expr,
                greeks_row_count=0,
                expression_count=0,
                fetch_attempted=False,
                fetch_skip_reason=skip_reason,
                expressions_artifact=artifact_path,
            )

        client, client_err = create_client_fn()
        if client is None:
            skip_reason = client_err or "credential_error:missing_credentials"
            out["candidate_loop_status"] = CandidateLoopStatus.PARKED_DATA_GAP.value
            out["hydration_status"] = HydrationStatus.PARKED_DATA_GAP.value
            out["data_gap_reason"] = skip_reason
            return AlpacaHydrationLoopResult(
                candidate_df=out,
                expressions_df=empty_expr,
                greeks_row_count=0,
                expression_count=0,
                fetch_attempted=False,
                fetch_skip_reason=skip_reason,
                expressions_artifact=artifact_path,
            )

        params = REPO_PAPER_LIVE_DEFAULTS
        fetch_attempted = True
        greeks_rows, _, _diag, _plans = stage_greeks_fn(
            specs,
            symbol_source="sg_morning_candidates",
            fetch=True,
            client=client,
            dte_min=params.dte_min,
            dte_max=params.dte_max,
            strike_buffer_pct=params.strike_buffer_pct,
            risk_free_rate=0.01,
            allow_bs_fallback=False,
            fallback_volatility_proxy=None,
            min_time_to_expiry_days=None,
            max_contracts_per_symbol=None,
        )
    else:
        skip_reason = "fetch_disabled"

    quote_rows = quote_rows_from_greeks_candidates(greeks_rows)
    if fetch_attempted and not quote_rows:
        out["candidate_loop_status"] = CandidateLoopStatus.PARKED_DATA_GAP.value
        out["hydration_status"] = HydrationStatus.NO_CHAIN_AVAILABLE.value
        out["data_gap_reason"] = "alpaca_quote_hydration_incomplete"
        return AlpacaHydrationLoopResult(
            candidate_df=out,
            expressions_df=empty_expr,
            greeks_row_count=len(greeks_rows),
            expression_count=0,
            fetch_attempted=fetch_attempted,
            fetch_skip_reason="no_quote_rows",
            expressions_artifact=artifact_path,
        )

    if not fetch:
        out["data_gap_reason"] = skip_reason or "fetch_disabled"
        return AlpacaHydrationLoopResult(
            candidate_df=out,
            expressions_df=empty_expr,
            greeks_row_count=0,
            expression_count=0,
            fetch_attempted=False,
            fetch_skip_reason=skip_reason or "fetch_disabled",
            expressions_artifact=artifact_path,
        )

    params = REPO_PAPER_LIVE_DEFAULTS
    expressions = generate_spread_candidates(
        quote_rows,
        structures=DEBIT_STRUCTURE_FILTER,
        max_bid_ask_spread_pct=params.max_bid_ask_spread_pct,
        max_per_underlying_date=None,
        limit=None,
        try_builder=True,
    )
    by_sym = _expressions_by_symbol(expressions)

    all_expression_records: list[dict[str, object]] = []
    updated_rows: list[dict[str, object]] = []
    for _, row in out.iterrows():
        row_dict = row.to_dict()
        sym = str(row_dict.get("symbol", "")).strip().upper()
        sym_exprs = by_sym.get(sym, [])
        expr_records = rank_expressions_for_candidate(sym_exprs, candidate_row=row_dict)
        all_expression_records.extend(expr_records)

        primary, alternates = _pick_primary_from_records(expr_records)
        row_dict["expression_count"] = len(expr_records)
        row_dict["alternate_expression_count"] = sum(
            1
            for r in alternates
            if str(r.get("expression_status", "")) == SpreadExpressionStatus.ALTERNATE.value
        )

        if primary is None:
            row_dict["candidate_loop_status"] = CandidateLoopStatus.NO_VIABLE_EXPRESSION.value
            row_dict["hydration_status"] = HydrationStatus.NO_VIABLE_EXPRESSION.value
            row_dict["selection_reason"] = (
                "candidate retained; no paper-tradable expression after expression search"
            )
            row_dict["data_gap_reason"] = "no_viable_expression_after_search"
            row_dict["primary_expression_id"] = ""
            row_dict["watch_expression_id"] = ""
            updated_rows.append(row_dict)
            continue

        primary_status = str(primary.get("expression_status", "")).strip()
        row_dict.update(_apply_primary_to_row(row, primary))
        row_dict["dealer_weighted_score"] = primary.get("dealer_weighted_score", "")
        row_dict["dealer_gate_tier"] = primary.get("dealer_gate_tier", "")
        row_dict["rr_baseline_required"] = primary.get("rr_baseline_required", "")
        row_dict["rr_dealer_required"] = primary.get("rr_dealer_required", "")
        row_dict["pmp_baseline_max"] = primary.get("pmp_baseline_max", "")
        row_dict["pmp_dealer_max"] = primary.get("pmp_dealer_max", "")

        if primary_status == SpreadExpressionStatus.WATCH.value:
            row_dict["primary_expression_id"] = ""
            row_dict["watch_expression_id"] = primary.get("expression_id", "")
            row_dict["candidate_loop_status"] = CandidateLoopStatus.WATCH_EXPRESSION_AVAILABLE.value
            row_dict["hydration_status"] = HydrationStatus.PARTIAL_HYDRATION.value
            row_dict["selection_reason"] = str(
                primary.get("expression_reason", "")
                or "watch expression available; no primary tier pass"
            )
            updated_rows.append(row_dict)
            continue

        row_dict["primary_expression_id"] = primary.get("expression_id", "")
        row_dict["watch_expression_id"] = ""
        if int(row_dict.get("alternate_expression_count", 0) or 0) > 0:
            row_dict["candidate_loop_status"] = CandidateLoopStatus.ALTERNATES_AVAILABLE.value
            row_dict["hydration_status"] = HydrationStatus.HYDRATED.value
            row_dict["selection_reason"] = "Primary expression selected; alternate expression retained"
        else:
            row_dict["candidate_loop_status"] = CandidateLoopStatus.PRIMARY_EXPRESSION_SELECTED.value
            row_dict["hydration_status"] = HydrationStatus.HYDRATED.value
            row_dict["selection_reason"] = "Primary expression selected"
        updated_rows.append(row_dict)

    expressions_df = expressions_to_dataframe(all_expression_records)
    if expressions_output_path is not None:
        out_path = Path(expressions_output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        expressions_df.to_csv(out_path, index=False)
        artifact_path = str(out_path)

    result_df = pd.DataFrame(updated_rows)
    return AlpacaHydrationLoopResult(
        candidate_df=result_df,
        expressions_df=expressions_df,
        greeks_row_count=len(greeks_rows),
        expression_count=len(expressions),
        fetch_attempted=fetch_attempted,
        fetch_skip_reason=skip_reason,
        expressions_artifact=artifact_path,
    )
