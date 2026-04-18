from __future__ import annotations

import pandas as pd

from qops.bridge.flags import build_candidate_flags
from qops.bridge.models import ChatGptCandidatePayload


def _parse_notes(value: object) -> tuple[str, ...]:
    if value is None or pd.isna(value):
        return ()
    return tuple(part.strip() for part in str(value).split("|") if part.strip())


def _optional_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _optional_confidence(value: object) -> float | int | None:
    if value is None or pd.isna(value):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f.is_integer():
        return int(f)
    return f


def _optional_regime_label(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned


def _build_market_context(trade_date: str, spy_df: pd.DataFrame | None) -> dict:
    if spy_df is None or spy_df.empty:
        return {
            "trade_date": trade_date,
            "spy_close": None,
            "spy_vol_trigger": None,
            "gamma_regime": None,
            "above_vol_trigger": None,
        }

    match = spy_df[spy_df["trade_date"].astype(str) == str(trade_date)]
    if match.empty:
        return {
            "trade_date": trade_date,
            "spy_close": None,
            "spy_vol_trigger": None,
            "gamma_regime": None,
            "above_vol_trigger": None,
        }

    row = match.iloc[-1]
    return {
        "trade_date": str(row["trade_date"]),
        "spy_close": row.get("close"),
        "spy_vol_trigger": row.get("vol_trigger"),
        "gamma_regime": row.get("gamma_regime"),
        "above_vol_trigger": row.get("above_vol_trigger"),
    }


def _empty_chain_context() -> dict:
    return {
        "nearest_expiration": None,
        "highest_oi_strike": None,
        "total_call_oi": None,
        "total_put_oi": None,
        "dominant_side": None,
        "concentration_near_spot": None,
        "movement_bias": None,
    }


def build_chatgpt_payloads(
    df: pd.DataFrame,
    *,
    spy_df: pd.DataFrame | None = None,
) -> list[ChatGptCandidatePayload]:
    """Build ChatGPT-ready candidate payloads from processed SpotGamma rows.

    Optional SPY rows are matched on ``trade_date``; missing matches yield
    ``None`` fields in ``market_context``. ``chain_context`` is always the
    empty stub for later MCP enrichment.

    Args:
        df: Validated processed SpotGamma DataFrame.
        spy_df: Optional SPY market context store (CSV as DataFrame).

    Returns:
        One ``ChatGptCandidatePayload`` per input row, in iteration order.
    """
    payloads: list[ChatGptCandidatePayload] = []

    overlap_map: dict[tuple[str, str], bool] = {}
    grouped = df.groupby(["trade_date", "symbol"])["source_type"].nunique()
    for (trade_date, symbol), count in grouped.items():
        overlap_map[(str(trade_date), str(symbol))] = int(count) > 1

    for _, row in df.iterrows():
        trade_date = str(row["trade_date"])
        symbol = str(row["symbol"])
        flags = build_candidate_flags(
            row=row.to_dict(),
            cross_file_overlap=overlap_map[(trade_date, symbol)],
        )

        payloads.append(
            ChatGptCandidatePayload(
                symbol=symbol,
                trade_date=trade_date,
                source_type=str(row["source_type"]),
                price=float(row["price"]),
                vol_trigger=_optional_float(row.get("vol_trigger")),
                call_wall=_optional_float(row.get("call_wall")),
                put_wall=_optional_float(row.get("put_wall")),
                gamma_ratio=_optional_float(row.get("gamma_ratio")),
                vrp=_optional_float(row.get("vrp")),
                vrp_z=_optional_float(row.get("vrp_z")),
                iv_rank=_optional_float(row.get("iv_rank")),
                regime_label=_optional_regime_label(row.get("regime_label")),
                confidence=_optional_confidence(row.get("confidence")),
                notes=_parse_notes(row.get("notes")),
                flags=flags,
                market_context=_build_market_context(trade_date, spy_df),
                chain_context=_empty_chain_context(),
            )
        )

    return payloads
