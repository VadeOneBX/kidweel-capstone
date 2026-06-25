"""Default spread skeptic advisory pattern (language only)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from qops.schemas.candidate_loop import SpreadExpressionStatus
from qops.schemas.playbook import AllowedPlaybook

_VIABLE_STATUSES = frozenset(
    {
        SpreadExpressionStatus.PRIMARY.value,
        SpreadExpressionStatus.ALTERNATE.value,
        SpreadExpressionStatus.WATCH.value,
        SpreadExpressionStatus.FAILED_EXPRESSION.value,
    }
)


@dataclass(frozen=True, slots=True)
class SpreadSkepticNote:
    expression_id: str
    symbol: str
    expression_status: str
    interesting_because: str
    but_challenge: str
    operator_check: str
    promotion_condition: str
    spread_skeptic_flag: bool
    spread_skeptic_reason: str
    macro_overlay: str


def _primary_rr_by_symbol(df: pd.DataFrame) -> dict[str, float]:
    primaries = df[df["expression_status"].astype(str) == SpreadExpressionStatus.PRIMARY.value]
    out: dict[str, float] = {}
    for _, row in primaries.iterrows():
        sym = str(row.get("symbol", "")).strip().upper()
        rr = pd.to_numeric(row.get("rr_actual"), errors="coerce")
        if sym and pd.notna(rr):
            out[sym] = float(rr)
    return out


def _wider_spread_exists(df: pd.DataFrame, symbol: str, primary_width: float | None) -> bool:
    sym_df = df[df["symbol"].astype(str).str.upper() == symbol.upper()]
    widths = pd.to_numeric(sym_df.get("width"), errors="coerce")
    if primary_width is None or widths.isna().all():
        return False
    return bool((widths > float(primary_width)).any())


def build_spread_skeptic_note(
    row: pd.Series,
    *,
    primary_rr: float | None,
    macro_posture: str,
    spot: float | None,
    wider_alternate_exists: bool,
) -> SpreadSkepticNote:
    sym = str(row.get("symbol", "")).strip().upper()
    expr_id = str(row.get("expression_id", "") or "")
    status = str(row.get("expression_status", "") or "")
    structure = str(row.get("structure", "") or "")
    long_strike = row.get("long_strike")
    short_strike = row.get("short_strike")
    rr = pd.to_numeric(row.get("rr_actual"), errors="coerce")
    breakeven = pd.to_numeric(row.get("breakeven"), errors="coerce")
    debit = pd.to_numeric(row.get("debit"), errors="coerce")
    max_profit = pd.to_numeric(row.get("max_profit"), errors="coerce")
    bid_ask = str(row.get("bid_ask_quality", "") or "").upper()
    width = pd.to_numeric(row.get("width"), errors="coerce")
    short_bid = pd.to_numeric(row.get("short_leg_bid"), errors="coerce")
    short_spread_pct = pd.to_numeric(row.get("short_leg_ask_spread_pct"), errors="coerce")

    strike_label = ""
    if pd.notna(long_strike) and pd.notna(short_strike):
        strike_label = f"{long_strike}/{short_strike}"

    interesting = (
        f"the {sym} {strike_label} {structure.replace('_', ' ').lower()} "
        f"offers a defined-risk expression"
    )
    if pd.notna(rr):
        interesting = (
            f"the {sym} {strike_label} spread offers reward/risk near {float(rr):.2f}"
        )
        if primary_rr is not None and float(rr) >= 2.0 * primary_rr and status != SpreadExpressionStatus.PRIMARY.value:
            interesting = (
                f"the {sym} {strike_label} spread offers materially higher reward/risk "
                f"than the selected primary"
            )
    if status == SpreadExpressionStatus.PRIMARY.value and strike_label:
        interesting = (
            f"the selected {sym} {strike_label} bull call spread is clean, narrow, "
            f"and dealer-aligned"
        )

    challenges: list[str] = []
    reasons: list[str] = []

    if bid_ask in {"POOR", "FAIL", "UNKNOWN"}:
        challenges.append("quote quality is uncertain or wide")
        reasons.append("bid_ask_quality_weak")
    if pd.notna(short_bid) and float(short_bid) <= 0.02:
        challenges.append(
            f"the short leg is quoted near {float(short_bid):.2f} with fragile fill quality"
        )
        reasons.append("short_leg_bid_thin")
    if pd.notna(short_spread_pct) and float(short_spread_pct) > 40.0:
        challenges.append(
            f"the short leg bid/ask spread is {float(short_spread_pct):.1f}% wide"
        )
        reasons.append("short_leg_spread_wide")
    if (
        primary_rr is not None
        and pd.notna(rr)
        and status != SpreadExpressionStatus.PRIMARY.value
        and float(rr) >= 2.0 * primary_rr
    ):
        challenges.append(
            "the improvement may depend on thin short-leg liquidity or fragile fill quality"
        )
        reasons.append("non_primary_rr_2x_primary")
    if (
        structure == AllowedPlaybook.BULL_CALL_SPREAD.value
        and spot is not None
        and pd.notna(breakeven)
        and float(breakeven) > float(spot)
    ):
        challenges.append(
            "breakeven sits above current spot, so directional movement is still required"
        )
        reasons.append("breakeven_above_spot")
    if status == SpreadExpressionStatus.PRIMARY.value and wider_alternate_exists:
        challenges.append(
            "it may not represent the best available payout in the same expiration"
        )
        reasons.append("primary_narrow_wider_exists")
    if pd.notna(max_profit) and pd.notna(debit) and float(debit) > 0 and float(debit) < 0.15:
        if float(max_profit) / float(debit) > 8.0:
            challenges.append("max profit is high relative to a very low debit")
            reasons.append("high_payout_low_debit")

    macro_gate_phrase = (
        "the AM note has not yet cleared the macro context gate"
        if "incomplete" in macro_posture.lower() or "withheld" in macro_posture.lower()
        else f"the AM note posture is {macro_posture or 'reviewed'}"
    )

    if not challenges:
        but_challenge = (
            f"paper approval still requires macro context, quote realism, and frontier comparison. "
            f"{macro_gate_phrase}."
        )
    else:
        joined = "; ".join(challenges)
        but_challenge = f"{joined.capitalize()}; {macro_gate_phrase}."

    operator_check = "compare against wider wings and confirm short-leg liquidity before paper approval."
    if "breakeven_above_spot" in reasons:
        operator_check = "compare breakeven to current price, call wall, and expected move."
    elif "bid_ask" in " ".join(challenges):
        operator_check = "confirm the short leg has real liquidity near the displayed bid."

    promotion = "retain as frontier candidate unless quote quality and fill realism confirm the setup."
    if status == SpreadExpressionStatus.PRIMARY.value:
        promotion = (
            "approve only if wider spreads fail liquidity or fill realism checks "
            "and AM note context is ready."
        )
    elif status != SpreadExpressionStatus.PRIMARY.value and primary_rr is not None and pd.notna(rr):
        promotion = (
            "retain as RR frontier unless the short leg can fill cleanly and debit stays "
            "near theoretical value."
        )

    macro_overlay = (
        f"But {macro_gate_phrase}, and directional spreads require stronger support from "
        f"wall proximity, liquidity, and frontier comparison."
    )

    flag = bool(reasons)
    return SpreadSkepticNote(
        expression_id=expr_id,
        symbol=sym,
        expression_status=status,
        interesting_because=f"That's interesting because {interesting}.",
        but_challenge=f"But {but_challenge.lstrip('But ')}",
        operator_check=f"Operator check: {operator_check}",
        promotion_condition=f"Promotion condition: {promotion}",
        spread_skeptic_flag=flag,
        spread_skeptic_reason="|".join(reasons) if reasons else "default_skeptic_review",
        macro_overlay=macro_overlay,
    )


def build_spread_skeptic_notes(
    expressions_df: pd.DataFrame,
    *,
    macro_posture: str,
    spot_by_symbol: dict[str, float] | None = None,
) -> list[SpreadSkepticNote]:
    if expressions_df.empty:
        return []
    df = expressions_df.copy()
    df = df[df["expression_status"].astype(str).isin(_VIABLE_STATUSES)]
    if df.empty:
        return []

    primary_rr = _primary_rr_by_symbol(df)
    notes: list[SpreadSkepticNote] = []
    for _, row in df.iterrows():
        sym = str(row.get("symbol", "")).strip().upper()
        spot = (spot_by_symbol or {}).get(sym)
        width = pd.to_numeric(row.get("width"), errors="coerce")
        prim_w = None
        if sym in primary_rr:
            prim_rows = df[
                (df["symbol"].astype(str).str.upper() == sym)
                & (df["expression_status"].astype(str) == SpreadExpressionStatus.PRIMARY.value)
            ]
            if not prim_rows.empty:
                prim_w = pd.to_numeric(prim_rows.iloc[0].get("width"), errors="coerce")
        wider = _wider_spread_exists(df, sym, float(prim_w) if pd.notna(prim_w) else None)
        notes.append(
            build_spread_skeptic_note(
                row,
                primary_rr=primary_rr.get(sym),
                macro_posture=macro_posture,
                spot=spot,
                wider_alternate_exists=wider,
            )
        )
    return notes
