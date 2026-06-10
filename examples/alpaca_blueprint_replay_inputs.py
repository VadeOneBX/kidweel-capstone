#!/usr/bin/env python3
"""SpotGamma-ready rows → Alpaca blueprint option symbol request plan (SG-BT-C4A).

Run:
  PYTHONPATH=src python examples/alpaca_blueprint_replay_inputs.py --rebuild-if-missing --no-write --limit 25
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qops.backtest.alpaca_blueprint_adapter import (
    blueprint_plan_to_dataframe,
    build_blueprint_request_plan,
    filter_ready_for_fetch,
    load_availability_plan,
    summarize_blueprint_plan,
)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description="Alpaca 0DTE blueprint-shaped option request plan for SpotGamma replay"
    )
    p.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/alpaca_replay_input_plan.csv"),
    )
    p.add_argument(
        "--candidates",
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
        help="Rebuild availability plan from candidates when --input CSV is absent",
    )
    p.add_argument("--dte-min", type=int, default=0)
    p.add_argument("--dte-max", type=int, default=7)
    p.add_argument("--strike-buffer-pct", type=float, default=0.03)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/alpaca_blueprint_replay_plan.csv"),
    )
    p.add_argument("--no-write", action="store_true")
    ns = p.parse_args(argv)

    availability, plan_source = load_availability_plan(
        input_csv=ns.input,
        candidates_csv=ns.candidates,
        spotgamma_root=ns.spotgamma_root,
        rebuild_if_missing=ns.rebuild_if_missing,
        dte_min=ns.dte_min,
        dte_max=ns.dte_max,
    )
    ready = filter_ready_for_fetch(availability)
    request_plans = build_blueprint_request_plan(
        ready,
        dte_min=ns.dte_min,
        dte_max=ns.dte_max,
        strike_buffer_pct=ns.strike_buffer_pct,
        limit=ns.limit,
    )
    summary = summarize_blueprint_plan(len(ready), request_plans)

    print("Alpaca blueprint replay request plan (no fetch)")
    print("=============================================")
    print(f"availability_plan_source: {plan_source}")
    print(f"ready_for_fetch_input_count: {summary['ready_for_fetch_input_count']}")
    print(f"request_plan_row_count: {summary['request_plan_row_count']}")
    print(f"symbols_count: {summary['symbol_count']}")
    print(f"date_range: {summary['date_min']} .. {summary['date_max']}")
    print(f"dte_window: {summary['dte_min']} .. {summary['dte_max']}")
    print("expiration_window_samples:")
    print(json.dumps(summary["expiration_window_samples"], indent=2))
    print(
        f"strike_window_summary: lower_min={summary['strike_lower_min']} "
        f"upper_max={summary['strike_upper_max']} "
        f"(buffer_pct={ns.strike_buffer_pct})"
    )

    if not ns.no_write and request_plans:
        ns.output.parent.mkdir(parents=True, exist_ok=True)
        blueprint_plan_to_dataframe(request_plans).to_csv(ns.output, index=False)
        print(f"wrote: {ns.output.resolve()}")
    elif ns.no_write:
        print("write: skipped (--no-write)")


if __name__ == "__main__":
    main()
