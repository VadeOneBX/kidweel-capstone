#!/usr/bin/env python3
"""Stage Alpaca-first greeks rows for narrowed blueprint plans (ALPACA-GREEKS-C1).

Run:
  PYTHONPATH=src python examples/alpaca_greeks_candidate_stage.py --rebuild-if-missing --no-write --limit 10
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from qops.backtest.alpaca_greeks_layer import (
    greeks_candidates_to_dataframe,
    load_blueprint_request_plans,
    stage_greeks_for_plans,
    summarize_greeks_staging,
    try_create_option_client,
)


def _safe_load_env() -> None:
    try:
        load_dotenv()
    except PermissionError:
        pass


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Alpaca greeks staging for blueprint-narrowed candidates")
    p.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/alpaca_blueprint_replay_plan.csv"),
    )
    p.add_argument(
        "--availability",
        type=Path,
        default=Path("data/processed/alpaca_replay_input_plan.csv"),
    )
    p.add_argument(
        "--candidates",
        type=Path,
        default=Path("data/processed/spotgamma_replay_candidates.csv"),
    )
    p.add_argument("--spotgamma-root", type=Path, default=Path("data/spotgamma"))
    p.add_argument("--rebuild-if-missing", action="store_true")
    p.add_argument("--no-write", action="store_true")
    p.add_argument("--fetch", action="store_true", help="Read-only Alpaca option chain snapshot fetch")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--dte-min", type=int, default=0)
    p.add_argument("--dte-max", type=int, default=7)
    p.add_argument("--strike-buffer-pct", type=float, default=0.03)
    p.add_argument("--risk-free-rate", type=float, default=0.05)
    p.add_argument(
        "--allow-bs-fallback",
        action="store_true",
        help="Compute BS/BSM greeks when Alpaca snapshot greeks are missing",
    )
    p.add_argument(
        "--fallback-volatility-proxy",
        type=float,
        default=None,
        help="Explicit IV proxy for BS fallback (marked on row); not used without --allow-bs-fallback",
    )
    p.add_argument(
        "--min-time-to-expiry-days",
        type=float,
        default=None,
        help="Optional minimum T floor in days for BS (0DTE); omit to fail closed on T<=0",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/alpaca_greeks_candidates.csv"),
    )
    ns = p.parse_args(argv)

    plans, plan_source = load_blueprint_request_plans(
        input_csv=ns.input,
        availability_csv=ns.availability,
        candidates_csv=ns.candidates,
        spotgamma_root=ns.spotgamma_root,
        rebuild_if_missing=ns.rebuild_if_missing,
        dte_min=ns.dte_min,
        dte_max=ns.dte_max,
        strike_buffer_pct=ns.strike_buffer_pct,
        limit=ns.limit,
    )

    client = None
    client_error: str | None = None
    if ns.fetch:
        _safe_load_env()
        client, client_error = try_create_option_client()

    candidates, fetch_attempted = stage_greeks_for_plans(
        plans,
        fetch=ns.fetch and client is not None,
        client=client,
        risk_free_rate=ns.risk_free_rate,
        allow_bs_fallback=ns.allow_bs_fallback,
        fallback_volatility_proxy=ns.fallback_volatility_proxy,
        min_time_to_expiry_days=ns.min_time_to_expiry_days,
    )
    summary = summarize_greeks_staging(len(plans), candidates, fetch_attempted=fetch_attempted)

    print("Alpaca greeks candidate staging (no approval, no execution)")
    print("============================================================")
    print(f"blueprint_plan_source: {plan_source}")
    print(f"blueprint_input_rows: {summary['blueprint_input_rows']}")
    print(f"greeks_candidate_rows: {summary['greeks_candidate_rows']}")
    print(f"fetch_requested: {ns.fetch}")
    print(f"fetch_attempted: {summary['fetch_attempted']}")
    if client_error:
        print(f"fetch_client: skipped ({client_error})")
    print("greeks_source_counts:")
    print(json.dumps(summary["greeks_source_counts"], indent=2))
    print("greeks_status_counts:")
    print(json.dumps(summary["greeks_status_counts"], indent=2))
    print(f"missing_or_invalid_count: {summary['missing_or_invalid_count']}")

    if not ns.no_write and candidates:
        ns.output.parent.mkdir(parents=True, exist_ok=True)
        greeks_candidates_to_dataframe(candidates).to_csv(ns.output, index=False)
        print(f"wrote: {ns.output.resolve()}")
    elif ns.no_write:
        print("write: skipped (--no-write)")


if __name__ == "__main__":
    main()
