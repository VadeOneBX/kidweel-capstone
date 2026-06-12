#!/usr/bin/env python3
"""Build paper payload candidates from paper_approval_candidates.csv (PAYLOAD-C1)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qops.execution.paper_payload_candidate import (
    build_paper_payload_candidates,
    load_paper_approval_rows,
    paper_payload_to_dataframe,
    summarize_paper_payload_candidates,
)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Paper payload candidates from paper approval rows")
    p.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/paper_approval_candidates.csv"),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/paper_payload_candidates.csv"),
    )
    p.add_argument("--no-write", action="store_true")
    p.add_argument("--limit", type=int, default=50)
    ns = p.parse_args(argv)

    rows = load_paper_approval_rows(ns.input)
    if not rows:
        print("Paper payload candidate build (PAYLOAD-C1)")
        print("==========================================")
        print(f"input_approval_candidates: 0 ({ns.input} missing or empty)")
        print("note: run examples/build_paper_approval_candidates.py first")
        return

    candidates = build_paper_payload_candidates(rows, limit=ns.limit)
    limited_rows = rows[: len(candidates)] if ns.limit else rows
    summary = summarize_paper_payload_candidates(len(limited_rows), candidates)

    print("Paper payload candidate build (PAYLOAD-C1)")
    print("==========================================")
    print(f"input_approval_candidates: {summary['input_approval_candidates']}")
    print(f"approved_for_paper_review_input_rows: {summary['approved_for_paper_review_input_rows']}")
    print(f"paper_payload_ready_count: {summary['paper_payload_ready_count']}")
    print(f"rejected_count: {summary['rejected_count']}")
    print(f"incomplete_count: {summary['incomplete_count']}")
    print("structure_counts_ready:")
    print(json.dumps(summary["structure_counts_ready"], indent=2))

    if not ns.no_write and candidates:
        ns.output.parent.mkdir(parents=True, exist_ok=True)
        paper_payload_to_dataframe(candidates).to_csv(ns.output, index=False)
        print(f"wrote: {ns.output.resolve()}")
    elif ns.no_write:
        print("write: skipped (--no-write)")


if __name__ == "__main__":
    main()
