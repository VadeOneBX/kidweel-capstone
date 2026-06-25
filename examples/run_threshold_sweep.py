#!/usr/bin/env python3
"""Threshold sensitivity sweep on staged spread candidates (THRESH-C1).

Run:
  PYTHONPATH=src python examples/run_threshold_sweep.py --no-write
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qops.analysis.threshold_sweep import (
    build_sweep_summary,
    run_threshold_sweep,
    scenario_results_to_dataframe,
    summary_to_json,
)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="THRESH-C1 candidate threshold sweep (analysis only)")
    p.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/spread_candidates.csv"),
    )
    p.add_argument(
        "--input-approvals",
        type=Path,
        default=Path("data/processed/paper_approval_candidates.csv"),
    )
    p.add_argument(
        "--input-greeks",
        type=Path,
        default=Path("data/processed/alpaca_greeks_candidates.csv"),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/threshold_sweep_results.csv"),
    )
    p.add_argument(
        "--summary-output",
        type=Path,
        default=Path("data/processed/threshold_sweep_summary.json"),
    )
    p.add_argument("--no-write", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    ns = p.parse_args(argv)

    rows, results = run_threshold_sweep(
        spreads_path=ns.input,
        approvals_path=ns.input_approvals,
        greeks_path=ns.input_greeks,
        limit=ns.limit,
    )
    inputs_present = {
        "spreads": ns.input.is_file(),
        "approvals": ns.input_approvals.is_file(),
        "greeks": ns.input_greeks.is_file(),
    }
    summary = build_sweep_summary(rows, results, inputs_present=inputs_present)

    def _pass(name: str) -> int:
        for r in results:
            if r.scenario_name == name:
                return r.pass_count
        return 0

    print("Threshold sweep (THRESH-C1)")
    print("=========================")
    print(f"total_input_rows: {len(rows)}")
    print(f"baseline_eligible_for_trade_review: {_pass('baseline')}")
    print(f"baseline_candidate_pass_count: {summary['baseline_candidate_pass_count']}")
    print(f"rr_gte_2_00 eligible: {_pass('rr_gte_2_00')}")
    print(f"ev_gte_0_00 eligible: {_pass('ev_gte_0_00')}")
    print(f"ev_gte_0_and_bid_ask_spread_pct_lte_0_50 eligible: {_pass('ev_gte_0_and_bid_ask_spread_pct_lte_0_50')}")
    print(f"ev_gte_0_and_rr_gte_2_00 eligible: {_pass('ev_gte_0_and_rr_gte_2_00')}")
    print(
        "ev_gte_0_and_rr_gte_2_00_and_bid_ask_spread_pct_lte_0_50 eligible: "
        f"{_pass('ev_gte_0_and_rr_gte_2_00_and_bid_ask_spread_pct_lte_0_50')}"
    )
    print("canonical_gates_unchanged: true")
    print("transport: none (no submit/close/live/order calls)")
    print()
    for r in results:
        print(
            f"  {r.scenario_name}: eligible={r.pass_count} "
            f"rate={r.pass_rate:.1%} required_fields_rows={r.rows_with_required_fields}"
        )

    highlights = summary.get("highlights", {})
    for key in (
        "ev_gte_0_and_rr_gte_2_00_and_bid_ask_spread_pct_lte_0_50",
        "ev_gte_0_and_rr_gte_2_00",
    ):
        block = highlights.get(key)
        if isinstance(block, dict) and block.get("top_10_survivors"):
            print(f"\ntop survivors ({key}):")
            print(json.dumps(block["top_10_survivors"][:5], indent=2))

    if not ns.no_write and results:
        ns.output.parent.mkdir(parents=True, exist_ok=True)
        scenario_results_to_dataframe(results).to_csv(ns.output, index=False)
        ns.summary_output.write_text(summary_to_json(summary), encoding="utf-8")
        print(f"\nwrote: {ns.output.resolve()}")
        print(f"wrote: {ns.summary_output.resolve()}")
    elif ns.no_write:
        print("\nwrite: skipped (--no-write)")


if __name__ == "__main__":
    main()
