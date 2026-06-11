#!/usr/bin/env python3
"""Generate math-gated spread candidates from staged Alpaca greeks rows (STRUCT-C2).

Run:
  PYTHONPATH=src python examples/generate_spread_candidates.py --no-write --limit 25
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qops.strategy.spread_candidate_generator import (
    generate_spread_candidates,
    load_greeks_quote_rows,
    spread_candidates_to_dataframe,
    summarize_spread_generation,
)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Math-gated spread candidate generation from greeks staging")
    p.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/alpaca_greeks_candidates.csv"),
    )
    p.add_argument("--no-write", action="store_true")
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/spread_candidates.csv"),
    )
    p.add_argument(
        "--structure",
        action="append",
        default=["ALL"],
        help="Repeatable; default ALL for canonical set",
    )
    p.add_argument("--max-bid-ask-spread-pct", type=float, default=0.25)
    p.add_argument("--max-per-underlying-date", type=int, default=None)
    p.add_argument("--limit", type=int, default=100)
    ns = p.parse_args(argv)

    rows = load_greeks_quote_rows(ns.input)
    if not rows:
        print("Spread candidate generation (STRUCT-C2)")
        print("====================================")
        print(f"input_rows: 0 ({ns.input} missing or empty)")
        print("spread_candidates_generated: 0")
        print(
            "note: STRUCT-C2 requires fetched Alpaca greeks/quote rows "
            "(see examples/alpaca_greeks_candidate_stage.py --fetch). No rows fabricated."
        )
        return

    candidates = generate_spread_candidates(
        rows,
        structures=ns.structure,
        max_bid_ask_spread_pct=ns.max_bid_ask_spread_pct,
        max_per_underlying_date=ns.max_per_underlying_date,
        limit=ns.limit,
    )
    summary = summarize_spread_generation(len(rows), candidates)

    print("Spread candidate generation (STRUCT-C2)")
    print("====================================")
    print(f"input_rows: {summary['input_rows']}")
    print(f"spread_candidates_generated: {summary['spread_candidates_generated']}")
    print(f"candidates_passing_math_gate: {summary['candidates_passing_math_gate']}")
    print(f"candidates_pass: {summary['candidates_pass']}")
    print(f"candidates_incomplete_missing_pmp: {summary['candidates_incomplete_missing_pmp']}")
    print("failure_reason_counts:")
    print(json.dumps(summary["failure_reason_counts"], indent=2))

    if not ns.no_write and candidates:
        ns.output.parent.mkdir(parents=True, exist_ok=True)
        spread_candidates_to_dataframe(candidates).to_csv(ns.output, index=False)
        print(f"wrote: {ns.output.resolve()}")
    elif ns.no_write:
        print("write: skipped (--no-write)")


if __name__ == "__main__":
    main()
