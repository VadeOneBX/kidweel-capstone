"""Export weekly SpotGamma DataFrames to Parquet, CSV, and report text."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import pandas as pd


class WeeklyExportPaths(TypedDict):
    """Output artifact paths from :func:`export_weekly_dataset`."""

    parquet: Path
    csv: Path
    report: Path


def _sort_weekly_df(df: pd.DataFrame) -> pd.DataFrame:
    """Sort by trade_date, source_type (SQUEEZE, VRP, REVERSE_VRP), symbol."""
    if df.empty:
        return df
    order = {"SQUEEZE": 0, "VRP": 1, "REVERSE_VRP": 2}
    out = df.assign(_src_order=df["source_type"].map(order))
    if out["_src_order"].isna().any():
        bad = out.loc[out["_src_order"].isna(), "source_type"].unique().tolist()
        raise ValueError(f"Unknown source_type values (cannot sort): {bad}")
    out = out.sort_values(["trade_date", "_src_order", "symbol"]).drop(columns=["_src_order"])
    return out.reset_index(drop=True)


def _export_stem(df: pd.DataFrame) -> str:
    """Basename stem for weekly files (single trade_date required when non-empty)."""
    if df.empty:
        return "spotgamma_weekly"
    u = pd.to_datetime(df["trade_date"], errors="raise").dt.normalize().unique()
    if len(u) != 1:
        raise ValueError(f"Weekly export requires exactly one trade_date, got {len(u)} distinct values")
    return f"spotgamma_weekly_{pd.Timestamp(u[0]).strftime('%Y%m%d')}"


def export_weekly_dataset(
    df: pd.DataFrame,
    output_dir: str | Path,
    report_text: str,
) -> WeeklyExportPaths:
    """Write sorted Parquet, CSV, and a text report under ``output_dir``.

    Args:
        df: Combined weekly dataset.
        output_dir: Directory to create or reuse.
        report_text: Full contents of the ``.txt`` summary (e.g. from
            :func:`qops.spotgamma.aggregate.build_aggregate_report`).

    Returns:
        Paths to parquet, csv, and report files.

    Raises:
        ValueError: If ``df`` contains more than one distinct ``trade_date`` when non-empty.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sorted_df = _sort_weekly_df(df)
    stem = _export_stem(sorted_df)
    pq = out_dir / f"{stem}.parquet"
    csv_path = out_dir / f"{stem}.csv"
    report_path = out_dir / f"{stem}_report.txt"

    sorted_df.to_parquet(pq, index=False)
    sorted_df.to_csv(csv_path, index=False)
    report_path.write_text(report_text, encoding="utf-8")

    return WeeklyExportPaths(parquet=pq, csv=csv_path, report=report_path)
