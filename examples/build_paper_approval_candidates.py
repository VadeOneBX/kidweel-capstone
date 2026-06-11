#!/usr/bin/env python3
"""Build paper approval candidates from spread_candidates.csv (APPROVAL-C1)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qops.risk.paper_approval import (
    build_paper_approval_candidates,
    load_spread_candidate_rows,
    paper_approval_to_dataframe,
    summarize_paper_approval_with_pass_count,
)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Paper approval layer from math-gated spread candidates")
    p.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/spread_candidates.csv"),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/paper_approval_candidates.csv"),
    )
    p.add_argument("--max-risk", type=float, default=600.0)
    p.add_argument("--no-write", action="store_true")
    p.add_argument("--limit", type=int, default=50)
    ns = p.parse_args(argv)

    rows = load_spread_candidate_rows(ns.input)
    if not rows:
        print("Paper approval candidate build (APPROVAL-C1)")
        print("============================================")
        print(f"input_spread_candidates: 0 ({ns.input} missing or empty)")
        print("note: run examples/generate_spread_candidates.py first")
        return

    candidates = build_paper_approval_candidates(rows, max_risk=ns.max_risk, limit=ns.limit)
    limited_rows = rows[: len(candidates)] if ns.limit else rows
    summary = summarize_paper_approval_with_pass_count(limited_rows, candidates)

    print("Paper approval candidate build (APPROVAL-C1)")
    print("============================================")
    print(f"input_spread_candidates: {summary['input_spread_candidates']}")
    print(f"candidate_pass_input_rows: {summary['candidate_pass_input_rows']}")
    print(f"approved_for_paper_review_count: {summary['approved_for_paper_review_count']}")
    print(f"rejected_count: {summary['rejected_count']}")
    print(f"incomplete_count: {summary['incomplete_count']}")
    print(f"max_loss_min: {summary['max_loss_min']}")
    print(f"max_loss_max: {summary['max_loss_max']}")
    print(f"max_loss_mean: {summary['max_loss_mean']}")
    print("pmp_source_counts:")
    print(json.dumps(summary["pmp_source_counts"], indent=2))
    print("pmp_confidence_counts:")
    print(json.dumps(summary["pmp_confidence_counts"], indent=2))

    if not ns.no_write and candidates:
        ns.output.parent.mkdir(parents=True, exist_ok=True)
        paper_approval_to_dataframe(candidates).to_csv(ns.output, index=False)
        print(f"wrote: {ns.output.resolve()}")
    elif ns.no_write:
        print("write: skipped (--no-write)")


if __name__ == "__main__":
    main()
