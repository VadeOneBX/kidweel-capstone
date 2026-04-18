from __future__ import annotations

import pandas as pd

from qops.context.models import MpcChainSummary

_REQUIRED_CHAIN_COLUMNS = ("expiration", "strike", "option_type", "open_interest")


def summarize_delayed_chain(
    df_chain: pd.DataFrame,
    *,
    symbol: str,
    spot_price: float | None = None,
) -> MpcChainSummary:
    """Summarize a delayed options chain snapshot (research enrichment only).

    Expects columns: ``expiration``, ``strike``, ``option_type`` (call/put, case-insensitive),
    ``open_interest``.

    Args:
        df_chain: Chain rows for one symbol snapshot.
        symbol: Underlying ticker.
        spot_price: Optional spot for concentration near strike (±5% band on nearest expiry).

    Returns:
        :class:`MpcChainSummary` aggregate.

    Raises:
        ValueError: If ``df_chain`` is empty, columns are missing, or OI cannot be aggregated.
    """
    if df_chain.empty:
        raise ValueError("empty delayed chain snapshot")
    missing = [c for c in _REQUIRED_CHAIN_COLUMNS if c not in df_chain.columns]
    if missing:
        raise ValueError(f"delayed chain snapshot missing columns: {missing}")

    df_chain = df_chain.copy()
    df_chain["_opt"] = df_chain["option_type"].astype(str).str.strip().str.lower()

    grouped_exp = (
        df_chain.groupby("expiration", as_index=False)["open_interest"]
        .sum()
        .sort_values(["expiration", "open_interest"], ascending=[True, False])
    )
    nearest_exp = str(grouped_exp.iloc[0]["expiration"])
    df_near = df_chain[df_chain["expiration"].astype(str) == nearest_exp].copy()

    call_oi = int(df_near.loc[df_near["_opt"] == "call", "open_interest"].fillna(0).sum())
    put_oi = int(df_near.loc[df_near["_opt"] == "put", "open_interest"].fillna(0).sum())

    strike_oi = (
        df_near.groupby("strike", as_index=False)["open_interest"]
        .sum()
        .sort_values("open_interest", ascending=False)
    )
    highest_oi_strike = float(strike_oi.iloc[0]["strike"]) if not strike_oi.empty else None

    if call_oi > put_oi:
        dominant_side = "CALLS"
        movement_bias = "UPSIDE_PRESSURE"
    elif put_oi > call_oi:
        dominant_side = "PUTS"
        movement_bias = "DOWNSIDE_PRESSURE"
    else:
        dominant_side = "BALANCED"
        movement_bias = "NEUTRAL"

    concentration_near_spot = None
    if spot_price is not None and not df_near.empty:
        band = df_near[(df_near["strike"] >= spot_price * 0.95) & (df_near["strike"] <= spot_price * 1.05)]
        total_oi = int(df_near["open_interest"].fillna(0).sum())
        band_oi = int(band["open_interest"].fillna(0).sum())
        concentration_near_spot = (band_oi / total_oi) if total_oi > 0 else None

    return MpcChainSummary(
        symbol=symbol,
        nearest_expiration=nearest_exp,
        highest_oi_strike=highest_oi_strike,
        total_call_oi=call_oi,
        total_put_oi=put_oi,
        dominant_side=dominant_side,
        concentration_near_spot=concentration_near_spot,
        movement_bias=movement_bias,
        note="delayed chain summary from MCP-fed snapshot",
    )
