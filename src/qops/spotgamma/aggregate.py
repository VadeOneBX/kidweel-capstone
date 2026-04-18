"""Aggregate SpotGamma records into DataFrames and text reports."""

from __future__ import annotations

import pandas as pd

from qops.spotgamma.models import SpotGammaRecord


def records_to_dataframe(records: list[SpotGammaRecord]) -> pd.DataFrame:
    """Convert normalized records to a single DataFrame for export.

    ``notes`` are serialized as pipe-delimited strings for columnar formats.

    Args:
        records: Rows from one or more normalized sheets.

    Returns:
        DataFrame with canonical columns (empty DataFrame if ``records`` is empty).
    """
    if not records:
        return pd.DataFrame(
            columns=[
                "trade_date",
                "symbol",
                "source_type",
                "price",
                "vol_trigger",
                "call_wall",
                "put_wall",
                "gamma_ratio",
                "vrp",
                "vrp_z",
                "iv_rank",
                "regime_label",
                "confidence",
                "notes",
            ]
        )
    rows: list[dict[str, object]] = []
    for r in records:
        rows.append(
            {
                "trade_date": r.trade_date,
                "symbol": r.symbol,
                "source_type": r.source_type,
                "price": r.price,
                "vol_trigger": r.vol_trigger,
                "call_wall": r.call_wall,
                "put_wall": r.put_wall,
                "gamma_ratio": r.gamma_ratio,
                "vrp": r.vrp,
                "vrp_z": r.vrp_z,
                "iv_rank": r.iv_rank,
                "regime_label": r.regime_label,
                "confidence": r.confidence,
                "notes": "|".join(r.notes) if r.notes else "",
            }
        )
    return pd.DataFrame(rows)


def build_aggregate_report(df: pd.DataFrame) -> str:
    """Build the weekly SpotGamma aggregate report string.

    Args:
        df: Combined weekly dataset (may be empty).

    Returns:
        Multi-line report suitable for console and ``.txt`` export.
    """
    lines: list[str] = []
    lines.append("Weekly SpotGamma Aggregate")
    n = len(df)
    lines.append(f"Rows: {n}")

    lines.append("By Source Type:")
    for st in ("SQUEEZE", "VRP", "REVERSE_VRP"):
        c = int((df["source_type"] == st).sum()) if not df.empty and "source_type" in df.columns else 0
        lines.append(f"  - {st}: {c}")

    lines.append("By Regime Label:")
    regime_order = ("SQUEEZE_UP", "SELL_PREMIUM", "BUY_PREMIUM", "NEUTRAL")
    if df.empty or "regime_label" not in df.columns:
        for rl in regime_order:
            lines.append(f"  - {rl}: 0")
    else:
        counts = df["regime_label"].fillna("").astype(str).value_counts()
        for rl in regime_order:
            lines.append(f"  - {rl}: {int(counts.get(rl, 0))}")

    lines.append("Cross-File Symbols:")
    if df.empty or "symbol" not in df.columns:
        lines.append("  (none)")
    else:
        by_sym = df.groupby("symbol")["source_type"].nunique()
        cross = sorted(by_sym[by_sym > 1].index.tolist())
        if not cross:
            lines.append("  (none)")
        else:
            for sym in cross:
                lines.append(f"  - {sym}")

    lines.append("Top Confidence Names By Source Type:")
    for st in ("SQUEEZE", "VRP", "REVERSE_VRP"):
        lines.append(f"  {st}:")
        if df.empty:
            lines.append("    (no rows)")
            continue
        sub = df[df["source_type"] == st].copy()
        if sub.empty:
            lines.append("    (no rows)")
            continue
        top = sub.sort_values("confidence", ascending=False).head(5)
        for _, row in top.iterrows():
            lines.append(f"    - {row['symbol']}: {float(row['confidence'])}")
    return "\n".join(lines) + "\n"
