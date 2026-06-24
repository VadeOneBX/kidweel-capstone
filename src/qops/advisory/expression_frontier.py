"""Expression frontier review — compare primary vs RR and payoff alternatives (advisory only)."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from qops.schemas.candidate_loop import SpreadExpressionStatus

FrontierRole = Literal[
    "PRIMARY_SELECTED",
    "BEST_RR",
    "BEST_EXPECTED_PAYOFF",
    "BEST_DEALER_ALIGNMENT",
    "PARETO_CANDIDATE",
    "REJECTED_FRONTIER",
]

PAPER_GATE_FRONTIER_REVIEW = "paper_gate:frontier_review_required"

_VIABLE_STATUSES = frozenset(
    {
        SpreadExpressionStatus.PRIMARY.value,
        SpreadExpressionStatus.ALTERNATE.value,
        SpreadExpressionStatus.WATCH.value,
    }
)

_TIER_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}
_BID_ASK_ORDER = {"PASS": 0, "UNKNOWN": 1, "POOR": 2, "FAIL": 3}


@dataclass(frozen=True, slots=True)
class SymbolFrontierSummary:
    symbol: str
    primary_expression_id: str
    primary_strikes: str
    primary_rr: float | None
    best_rr_expression_id: str
    best_rr: float | None
    best_rr_strikes: str
    operator_challenge_flag: bool
    operator_challenge_reason: str
    frontier_comparison_note: str
    expected_payoff_status: str


@dataclass(frozen=True, slots=True)
class ExpressionFrontierResult:
    expression_rows: list[dict[str, object]]
    symbol_summaries: list[SymbolFrontierSummary]
    challenged_symbols: frozenset[str]
    frontier_review_required_before_paper: bool


def manual_frontier_path(base_dir: Path, run_id: str) -> Path:
    return base_dir / "data/advisory" / f"{run_id}_manual_frontier_expressions.json"


def _load_manual_frontier(base_dir: Path, run_id: str) -> list[dict[str, object]]:
    path = manual_frontier_path(base_dir, run_id)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(data, dict) and isinstance(data.get("expressions"), list):
        return [x for x in data["expressions"] if isinstance(x, dict)]
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def _num(value: object) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _strike_key(
    symbol: str,
    expiration: str,
    long_strike: object,
    short_strike: object,
) -> str:
    return (
        f"{symbol.strip().upper()}|{str(expiration).strip()}|"
        f"{_num(long_strike)}|{_num(short_strike)}"
    )


def _expected_payoff(row: pd.Series) -> float | None:
    ev = _num(row.get("ev"))
    if ev is not None:
        return ev
    ev2 = _num(row.get("expected_value"))
    if ev2 is not None:
        return ev2
    pmp = _num(row.get("pmp"))
    max_profit = _num(row.get("max_profit"))
    max_loss = _num(row.get("max_loss"))
    if pmp is None or max_profit is None or max_loss is None:
        return None
    return pmp * max_profit - (1.0 - pmp) * max_loss


def _rr_frontier_eligible(row: pd.Series) -> bool:
    max_loss = _num(row.get("max_loss"))
    max_profit = _num(row.get("max_profit"))
    debit = _num(row.get("debit"))
    width = _num(row.get("width"))
    if not all(v is not None and v > 0 for v in (max_loss, max_profit, debit, width)):
        return False
    bid_ask = str(row.get("bid_ask_quality", "") or "").strip().upper()
    if bid_ask == "FAIL":
        return False
    short_bid = _num(row.get("short_leg_bid"))
    long_ask = _num(row.get("long_leg_ask"))
    if short_bid is not None and short_bid <= 0:
        return False
    if long_ask is not None and long_ask <= 0:
        return False
    quote_age = _num(row.get("quote_age_seconds"))
    if quote_age is not None and quote_age > 900:
        return False
    return True


def _dealer_sort_key(row: pd.Series) -> tuple[float, ...]:
    tier = str(row.get("dealer_gate_tier", "") or "").strip().upper()
    tier_rank = float(_TIER_ORDER.get(tier[:1] if tier else "", 9))
    dws = _num(row.get("dealer_weighted_score"))
    wall = _num(row.get("wall_proximity_score"))
    pmp = _num(row.get("pmp"))
    ba = str(row.get("bid_ask_quality", "") or "").strip().upper()
    ba_rank = float(_BID_ASK_ORDER.get(ba, 9))
    return (
        tier_rank,
        -(dws if dws is not None else -1.0),
        -(wall if wall is not None else -1.0),
        pmp if pmp is not None else 1.0,
        ba_rank,
    )


def _strike_label(row: pd.Series) -> str:
    lo = row.get("long_strike")
    hi = row.get("short_strike")
    if lo is not None and hi is not None and not (isinstance(lo, float) and math.isnan(lo)):
        return f"{lo}/{hi}"
    return ""


def _assign_frontier_role(
    *,
    is_primary: bool,
    dealer_rank: int,
    rr_rank: int | None,
    payoff_rank: int | None,
    rr_eligible: bool,
) -> FrontierRole:
    if is_primary:
        return "PRIMARY_SELECTED"
    if rr_rank == 1 and rr_eligible:
        return "BEST_RR"
    if payoff_rank == 1:
        return "BEST_EXPECTED_PAYOFF"
    if dealer_rank == 1:
        return "BEST_DEALER_ALIGNMENT"
    if rr_eligible and rr_rank is not None and rr_rank <= 3:
        return "PARETO_CANDIDATE"
    if not rr_eligible:
        return "REJECTED_FRONTIER"
    return "PARETO_CANDIDATE"


def _rank_series(values: list[tuple[int, float]]) -> dict[int, int]:
    """Map row index -> rank (1-based), higher value is better."""
    ordered = sorted(values, key=lambda x: x[1], reverse=True)
    ranks: dict[int, int] = {}
    for rank, (idx, _) in enumerate(ordered, start=1):
        ranks[idx] = rank
    return ranks


def _build_symbol_summary(
    symbol: str,
    sym_df: pd.DataFrame,
    enriched: list[dict[str, object]],
    manual_absent_reason: str | None,
) -> SymbolFrontierSummary:
    primary_rows = sym_df[
        sym_df["expression_status"].astype(str) == SpreadExpressionStatus.PRIMARY.value
    ]
    primary = primary_rows.iloc[0] if not primary_rows.empty else sym_df.iloc[0]
    primary_id = str(primary.get("expression_id", ""))
    primary_rr = _num(primary.get("rr_actual"))
    primary_strikes = _strike_label(primary)
    primary_width = _num(primary.get("width"))

    rr_eligible = sym_df[sym_df.apply(_rr_frontier_eligible, axis=1)]
    best_rr_row = primary
    if not rr_eligible.empty:
        best_rr_row = rr_eligible.loc[rr_eligible["rr_actual"].astype(float).idxmax()]

    best_rr = _num(best_rr_row.get("rr_actual"))
    best_rr_id = str(best_rr_row.get("expression_id", ""))
    best_rr_strikes = _strike_label(best_rr_row)

    payoff_available = any(_expected_payoff(sym_df.iloc[i]) is not None for i in range(len(sym_df)))
    payoff_status = "ranked" if payoff_available else "expected_payoff_unavailable"

    reasons: list[str] = []
    challenged = False

    if primary_rr is not None and best_rr is not None and best_rr_id != primary_id:
        if best_rr >= 2.0 * primary_rr:
            challenged = True
            reasons.append("non_primary_rr_2x_primary")

    primary_max_profit = _num(primary.get("max_profit"))
    primary_max_loss = _num(primary.get("max_loss"))
    for _, row in sym_df.iterrows():
        if str(row.get("expression_id")) == primary_id:
            continue
        mp = _num(row.get("max_profit"))
        ml = _num(row.get("max_loss"))
        if (
            mp is not None
            and primary_max_profit is not None
            and mp > primary_max_profit * 1.25
            and ml is not None
            and primary_max_loss is not None
            and ml <= primary_max_loss * 1.1
        ):
            challenged = True
            reasons.append("higher_max_profit_similar_risk")
            break

    if payoff_available:
        primary_payoff = _expected_payoff(primary)
        for _, row in sym_df.iterrows():
            if str(row.get("expression_id")) == primary_id:
                continue
            alt_payoff = _expected_payoff(row)
            if (
                primary_payoff is not None
                and alt_payoff is not None
                and alt_payoff > primary_payoff
            ):
                challenged = True
                reasons.append("higher_expected_payoff_than_primary")
                break

    if manual_absent_reason:
        challenged = True
        reasons.append(manual_absent_reason)

    if primary_width is not None:
        widths = pd.to_numeric(sym_df.get("width"), errors="coerce")
        wider = sym_df[widths > primary_width + 1e-9]
        wider_eligible = wider[wider.apply(_rr_frontier_eligible, axis=1)]
        if not wider_eligible.empty:
            challenged = True
            reasons.append("primary_narrow_wider_valid_spreads_exist")

    note = (
        f"{symbol} primary is valid but not proven optimal. "
        f"The selected {primary_strikes} spread is dealer-aligned and clean, "
        f"but wider structures such as {best_rr_strikes} may offer materially better reward/risk. "
        f"Operator frontier review required: compare the primary against the RR frontier "
        f"and verify short-leg liquidity before paper approval."
    )
    if manual_absent_reason:
        note = (
            f"{symbol} is active, but not yet clean for paper approval. "
            f"The scanner selected a narrow dealer-aligned spread. "
            f"Manual review found a wider higher-RR structure not present in the hydrated "
            f"expression set. Because that structure may depend on thin short-call liquidity "
            f"and a move through breakeven, review it as a frontier candidate rather than "
            f"blindly promoting the primary."
        )

    return SymbolFrontierSummary(
        symbol=symbol,
        primary_expression_id=primary_id,
        primary_strikes=primary_strikes,
        primary_rr=primary_rr,
        best_rr_expression_id=best_rr_id,
        best_rr=best_rr,
        best_rr_strikes=best_rr_strikes,
        operator_challenge_flag=challenged,
        operator_challenge_reason="|".join(dict.fromkeys(reasons)),
        frontier_comparison_note=note,
        expected_payoff_status=payoff_status,
    )


def build_expression_frontier(
    expressions_df: pd.DataFrame,
    *,
    base_dir: Path | None = None,
    run_id: str = "",
) -> ExpressionFrontierResult:
    if expressions_df.empty:
        return ExpressionFrontierResult(
            expression_rows=[],
            symbol_summaries=[],
            challenged_symbols=frozenset(),
            frontier_review_required_before_paper=False,
        )

    df = expressions_df.copy()
    df = df[df["expression_status"].astype(str).isin(_VIABLE_STATUSES)]
    if df.empty:
        return ExpressionFrontierResult(
            expression_rows=[],
            symbol_summaries=[],
            challenged_symbols=frozenset(),
            frontier_review_required_before_paper=False,
        )

    manual_entries = _load_manual_frontier(base_dir, run_id) if base_dir and run_id else []
    generated_keys: set[str] = set()
    for _, row in df.iterrows():
        generated_keys.add(
            _strike_key(
                str(row.get("symbol", "")),
                str(row.get("expiration", "")),
                row.get("long_strike"),
                row.get("short_strike"),
            )
        )

    manual_absent_by_symbol: dict[str, str] = {}
    for entry in manual_entries:
        sym = str(entry.get("symbol", "")).strip().upper()
        key = _strike_key(
            sym,
            str(entry.get("expiration", "")),
            entry.get("long_strike"),
            entry.get("short_strike"),
        )
        if key not in generated_keys:
            manual_absent_by_symbol[sym] = "manual_frontier_expression_absent_from_scan"

    enriched_rows: list[dict[str, object]] = []
    summaries: list[SymbolFrontierSummary] = []
    challenged: set[str] = set()

    for symbol, sym_df in df.groupby(df["symbol"].astype(str).str.upper()):
        sym_df = sym_df.reset_index(drop=True)
        if sym_df.empty:
            continue

        dealer_keys = [_dealer_sort_key(sym_df.iloc[i]) for i in range(len(sym_df))]
        dealer_order = sorted(range(len(sym_df)), key=lambda i: dealer_keys[i])
        dealer_ranks = {i: rank for rank, i in enumerate(dealer_order, start=1)}

        rr_indices = [i for i in range(len(sym_df)) if _rr_frontier_eligible(sym_df.iloc[i])]
        rr_ranks: dict[int, int] = {}
        if rr_indices:
            rr_vals = [(i, _num(sym_df.iloc[i].get("rr_actual")) or 0.0) for i in rr_indices]
            rr_ranks = _rank_series(rr_vals)

        payoff_indices = [i for i in range(len(sym_df)) if _expected_payoff(sym_df.iloc[i]) is not None]
        payoff_ranks: dict[int, int] = {}
        if payoff_indices:
            payoff_vals = [
                (i, _expected_payoff(sym_df.iloc[i]) or 0.0) for i in payoff_indices
            ]
            payoff_ranks = _rank_series(payoff_vals)

        summary = _build_symbol_summary(
            symbol,
            sym_df,
            enriched_rows,
            manual_absent_by_symbol.get(symbol),
        )
        summaries.append(summary)
        if summary.operator_challenge_flag:
            challenged.add(symbol)

        for i in range(len(sym_df)):
            row = sym_df.iloc[i]
            is_primary = (
                str(row.get("expression_status")) == SpreadExpressionStatus.PRIMARY.value
            )
            rr_eligible = _rr_frontier_eligible(row)
            role = _assign_frontier_role(
                is_primary=is_primary,
                dealer_rank=dealer_ranks.get(i, 99),
                rr_rank=rr_ranks.get(i),
                payoff_rank=payoff_ranks.get(i),
                rr_eligible=rr_eligible,
            )
            expr_challenged = summary.operator_challenge_flag
            expr_reason = summary.operator_challenge_reason
            if not is_primary:
                p_rr = summary.primary_rr
                rr = _num(row.get("rr_actual"))
                if p_rr is not None and rr is not None and rr >= 2.0 * p_rr:
                    expr_challenged = True
                    expr_reason = "|".join(
                        filter(None, [expr_reason, "non_primary_rr_2x_primary"])
                    )

            comparison = summary.frontier_comparison_note if is_primary else ""
            payload = {k: row[k] for k in row.index}
            payload.update(
                {
                    "frontier_role": role,
                    "dealer_rank": dealer_ranks.get(i),
                    "rr_rank": rr_ranks.get(i),
                    "expected_payoff_rank": payoff_ranks.get(i),
                    "operator_challenge_flag": expr_challenged,
                    "operator_challenge_reason": expr_reason,
                    "frontier_comparison_note": comparison,
                }
            )
            enriched_rows.append(payload)

    return ExpressionFrontierResult(
        expression_rows=enriched_rows,
        symbol_summaries=summaries,
        challenged_symbols=frozenset(challenged),
        frontier_review_required_before_paper=bool(challenged),
    )


def apply_frontier_paper_gate_to_audit(
    audit_df: pd.DataFrame,
    frontier: ExpressionFrontierResult,
) -> pd.DataFrame:
    if audit_df.empty or not frontier.frontier_review_required_before_paper:
        return audit_df

    out = audit_df.copy()
    for idx, row in out.iterrows():
        sym = str(row.get("symbol", "") or row.get("underlying", "")).strip().upper()
        if sym not in frontier.challenged_symbols:
            continue
        approval = str(row.get("paper_approval_status", "") or "").strip()
        classification = str(row.get("classification", "") or "").strip()
        if approval == "WITHHELD_PENDING_AM_NOTE":
            continue
        if approval != "APPROVED_FOR_PAPER_REVIEW" and classification != "APPROVED_PAPER":
            continue
        out.at[idx, "paper_approval_status"] = "WITHHELD_PENDING_FRONTIER_REVIEW"
        out.at[idx, "classification"] = "PAPER_GATE_WITHHELD"
        out.at[idx, "reject_reason"] = PAPER_GATE_FRONTIER_REVIEW

    return out


def format_expression_frontier_section(summaries: list[SymbolFrontierSummary], limit: int = 12) -> str:
    if not summaries:
        return "- (no expression frontier summaries — hydration may be pending)"
    lines: list[str] = []
    for summary in summaries[:limit]:
        flag = "yes" if summary.operator_challenge_flag else "no"
        lines.append(
            f"### {summary.symbol}\n\n"
            f"{summary.frontier_comparison_note}\n\n"
            f"- Primary: `{summary.primary_strikes}` RR `{summary.primary_rr}`\n"
            f"- RR frontier best: `{summary.best_rr_strikes}` RR `{summary.best_rr}`\n"
            f"- Operator challenge: **{flag}** (`{summary.operator_challenge_reason or 'none'}`)\n"
            f"- Expected payoff: `{summary.expected_payoff_status}`\n"
        )
    if len(summaries) > limit:
        lines.append(f"\n_(+{len(summaries) - limit} symbols in run_advisory JSON)_\n")
    return "\n".join(lines)
