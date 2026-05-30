#!/usr/bin/env python3
"""Plan Alpaca historical replay input availability for SpotGamma candidates (SG-BT-C3).

Run:
  PYTHONPATH=src python examples/alpaca_replay_input_availability.py --rebuild-if-missing --no-write
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qops.backtest.alpaca_replay_inputs import (
    build_availability_plan,
    fetch_historical_data_read_only,
    load_replay_candidates,
    plan_to_dataframe,
    summarize_availability_plan,
)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description="SpotGamma replay candidates → Alpaca historical input availability plan"
    )
    p.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/spotgamma_replay_candidates.csv"),
    )
    p.add_argument(
        "--spotgamma-root",
        type=Path,
        default=Path("data/spotgamma"),
    )
    p.add_argument(
        "--rebuild-if-missing",
        action="store_true",
        help="Rebuild candidates from ingest when --input CSV is absent",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/alpaca_replay_input_plan.csv"),
    )
    p.add_argument("--dte-min", type=int, default=0)
    p.add_argument("--dte-max", type=int, default=7)
    p.add_argument(
        "--fetch",
        action="store_true",
        help="Not implemented in C3 (read-only fetch is a future packet)",
    )
    p.add_argument("--no-write", action="store_true")
    ns = p.parse_args(argv)

    if ns.fetch:
        try:
            fetch_historical_data_read_only()
        except NotImplementedError as exc:
            raise SystemExit(str(exc)) from exc

    candidates, source = load_replay_candidates(
        input_csv=ns.input,
        spotgamma_root=ns.spotgamma_root,
        rebuild_if_missing=ns.rebuild_if_missing,
    )
    plans = build_availability_plan(candidates, dte_min=ns.dte_min, dte_max=ns.dte_max)
    summary = summarize_availability_plan(plans)

    print("Alpaca replay input availability (plan only)")
    print("===========================================")
    print(f"candidate_source: {source}")
    print(f"input_candidate_row_count: {len(candidates)}")
    print(f"availability_plan_row_count: {summary['plan_row_count']}")
    print(f"symbols_count: {summary['symbol_count']}")
    print(f"date_range: {summary['date_min']} .. {summary['date_max']}")
    print(f"ready_for_fetch_count: {summary['ready_for_fetch']}")
    print("availability_by_status:")
    print(json.dumps(summary["by_status"], indent=2, sort_keys=True))
    print("missing_requirements_summary:")
    print(json.dumps(summary["missing_requirements_summary"], indent=2, sort_keys=True))

    if not ns.no_write and plans:
        ns.output.parent.mkdir(parents=True, exist_ok=True)
        plan_to_dataframe(plans).to_csv(ns.output, index=False)
        print(f"wrote: {ns.output.resolve()}")
    elif ns.no_write:
        print("write: skipped (--no-write)")


if __name__ == "__main__":
    main()
