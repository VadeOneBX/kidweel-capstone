#!/usr/bin/env python3
"""Canonical backtest evidence refresh (BT-C3) — local CSVs only, no transport.

Run:
  PYTHONPATH=src python examples/run_canonical_backtest_refresh.py --no-write
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from qops.backtest.canonical_refresh import (
    CanonicalRefreshPaths,
    evidence_rows_to_dataframe,
    run_canonical_backtest_refresh,
    summary_to_json,
)


def _load_fixtures() -> list:
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from examples.backtest_sanity_run import build_bt_c1_sample  # noqa: PLC0415

    tagged = build_bt_c1_sample()
    return [(t.source, t.ctx) for t in tagged]


def _print_per_class(summary: dict) -> None:
    by_class = summary.get("evidence_rows_by_class", {})
    per = summary.get("per_class_summaries", {})
    print("Evidence by class (not blended)")
    print("===========================")
    for cls in sorted(by_class.keys()):
        count = by_class[cls]
        detail = per.get(cls, {})
        print(f"  {cls}: {count}")
        if detail:
            print(f"    candidate_pass: {detail.get('candidate_pass_count', 0)}")
            print(f"    realized_pnl_rows: {detail.get('realized_pnl_count', 0)}")
    print()


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="BT-C3 canonical evidence refresh (read-only)")
    p.add_argument(
        "--input-spreads",
        type=Path,
        default=Path("data/processed/spread_candidates.csv"),
    )
    p.add_argument(
        "--input-approvals",
        type=Path,
        default=Path("data/processed/paper_approval_candidates.csv"),
    )
    p.add_argument(
        "--input-payloads",
        type=Path,
        default=Path("data/processed/paper_payload_candidates.csv"),
    )
    p.add_argument(
        "--input-greeks",
        type=Path,
        default=Path("data/processed/alpaca_greeks_candidates.csv"),
    )
    p.add_argument(
        "--input-sg",
        type=Path,
        default=Path("data/processed/spotgamma_replay_candidates.csv"),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/canonical_backtest_refresh.csv"),
    )
    p.add_argument(
        "--summary-output",
        type=Path,
        default=Path("data/processed/canonical_backtest_summary.json"),
    )
    p.add_argument("--no-write", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument(
        "--include-fixture-evidence",
        action="store_true",
        help="Opt-in BT-C1 ReplayContext fixtures as FIXTURE_EVIDENCE",
    )
    p.add_argument(
        "--derive-spreads-if-missing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Derive spread rows in-memory from greeks when spread CSV absent",
    )
    ns = p.parse_args(argv)

    fixtures = _load_fixtures() if ns.include_fixture_evidence else None
    paths = CanonicalRefreshPaths(
        spreads=ns.input_spreads,
        approvals=ns.input_approvals,
        payloads=ns.input_payloads,
        greeks=ns.input_greeks,
        sg=ns.input_sg,
    )
    rows, summary = run_canonical_backtest_refresh(
        paths,
        derive_spreads_if_missing=ns.derive_spreads_if_missing,
        limit=ns.limit,
        fixture_tagged=fixtures,
    )

    print("Canonical backtest evidence refresh (BT-C3)")
    print("==========================================")
    print(f"total_rows_inspected: {summary['total_rows_inspected']}")
    print(f"candidates_generated: {summary['candidates_generated']}")
    print(f"candidates_passing_math: {summary['candidates_passing_math']}")
    print(f"candidates_passing_pmp_rr: {summary['candidates_passing_pmp_rr']}")
    print(f"candidates_passing_ev: {summary['candidates_passing_ev']}")
    print(f"candidate_pass_count: {summary['candidate_pass_count']}")
    print(f"approval_ready_count: {summary['approval_ready_count']}")
    print(f"payload_ready_count: {summary['payload_ready_count']}")
    print(f"trades_with_real_exit_pnl: {summary['trades_with_real_exit_pnl']}")
    print(f"missing_pmp_count: {summary['missing_pmp_count']}")
    print(f"missing_exit_count: {summary['missing_exit_count']}")
    _print_per_class(summary)
    print("advisory_group_counts:")
    print(json.dumps(summary["advisory_group_counts"], indent=2))
    print("rr_pmp_summary:")
    print(json.dumps(summary["rr_pmp_summary"], indent=2))
    print("top_squeeze_candidates_by_spread_delta:")
    print(json.dumps(summary["top_squeeze_candidates_by_spread_delta"], indent=2))
    if summary.get("limitations"):
        print("limitations:")
        for note in summary["limitations"]:
            print(f"  - {note}")
    print("transport: none (no submit/close/live/order calls)")

    if not ns.no_write and rows:
        ns.output.parent.mkdir(parents=True, exist_ok=True)
        evidence_rows_to_dataframe(rows).to_csv(ns.output, index=False)
        ns.summary_output.parent.mkdir(parents=True, exist_ok=True)
        ns.summary_output.write_text(summary_to_json(summary), encoding="utf-8")
        print(f"wrote: {ns.output.resolve()}")
        print(f"wrote: {ns.summary_output.resolve()}")
    elif ns.no_write:
        print("write: skipped (--no-write)")


if __name__ == "__main__":
    main()
