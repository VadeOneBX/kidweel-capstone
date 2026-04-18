"""CLI: ingest SpotGamma SQUEEZE / VRP / REVERSE_VRP XLSX exports for one trade date."""

from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path

from qops.spotgamma.aggregate import build_aggregate_report, records_to_dataframe
from qops.spotgamma.export import export_weekly_dataset
from qops.spotgamma.models import SpotGammaRecord
from qops.spotgamma.normalize import normalize_rows
from qops.spotgamma.readers import read_xlsx_table


def _parse_trade_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as e:
        raise ValueError(f"trade_date must be YYYY-MM-DD, got {s!r}") from e


def main(argv: list[str] | None = None) -> None:
    """Parse CLI args, load three XLSX files, normalize, aggregate, export, and print summary."""
    p = argparse.ArgumentParser(
        description="Build weekly SpotGamma candidate surface from three XLSX exports."
    )
    p.add_argument("--trade-date", required=True, help="Session date YYYY-MM-DD")
    p.add_argument("--squeeze", required=True, type=Path, help="Path to SQUEEZE XLSX")
    p.add_argument("--vrp", required=True, type=Path, help="Path to VRP XLSX")
    p.add_argument("--reverse-vrp", required=True, type=Path, help="Path to REVERSE_VRP XLSX")
    p.add_argument("--output-dir", required=True, type=Path, help="Directory for exports")
    p.add_argument(
        "--default-confidence",
        type=float,
        default=None,
        help="Use this confidence when the XLSX has no Confidence column (SpotGamma portal exports).",
    )
    ns = p.parse_args(argv)

    td = _parse_trade_date(ns.trade_date)
    dc = ns.default_confidence

    squeeze_df = read_xlsx_table(ns.squeeze)
    vrp_df = read_xlsx_table(ns.vrp)
    rev_df = read_xlsx_table(ns.reverse_vrp)

    records: list[SpotGammaRecord] = []
    records.extend(
        normalize_rows(squeeze_df, source_type="SQUEEZE", trade_date=td, default_confidence=dc)
    )
    records.extend(normalize_rows(vrp_df, source_type="VRP", trade_date=td, default_confidence=dc))
    records.extend(
        normalize_rows(rev_df, source_type="REVERSE_VRP", trade_date=td, default_confidence=dc)
    )

    df = records_to_dataframe(records)
    report = build_aggregate_report(df)
    paths = export_weekly_dataset(df, ns.output_dir, report)

    print(report, end="")
    print("Output paths:")
    print(f"  parquet: {paths['parquet']}")
    print(f"  csv:     {paths['csv']}")
    print(f"  report:  {paths['report']}")
    print(f"Final row count: {len(df)}")


if __name__ == "__main__":
    main()
