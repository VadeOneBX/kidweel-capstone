#!/usr/bin/env python3
"""Stage SpotGamma replay candidates from context corpus (SG-BT-C2).

Run:
  PYTHONPATH=src python examples/spotgamma_to_replay_candidates.py \\
    --input data/processed/spotgamma_context_sample.csv --no-write
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qops.backtest.spotgamma_replay_builder import (
    build_replay_candidates,
    candidates_to_dataframe,
    load_contexts,
    summarize_replay_candidates,
)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="SpotGamma context → replay candidate staging")
    p.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/spotgamma_context_sample.csv"),
        help="Normalized context CSV (optional if --include-raw rebuild)",
    )
    p.add_argument(
        "--spotgamma-root",
        type=Path,
        default=Path("data/spotgamma"),
        help="SpotGamma root for --include-raw rebuild",
    )
    p.add_argument(
        "--include-raw",
        action="store_true",
        help="Rebuild context from ingest when --input is missing",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/spotgamma_replay_candidates.csv"),
    )
    p.add_argument("--no-write", action="store_true")
    ns = p.parse_args(argv)

    input_csv = ns.input if ns.input.is_file() else None
    if input_csv is None and not ns.include_raw:
        raise SystemExit(
            f"Input not found: {ns.input}. Re-run with --include-raw to rebuild from ingest."
        )

    contexts = load_contexts(
        input_csv=input_csv,
        spotgamma_root=ns.spotgamma_root,
        include_raw=ns.include_raw,
    )
    candidates = build_replay_candidates(contexts)
    summary = summarize_replay_candidates(candidates)

    print("SpotGamma replay candidates (staging only)")
    print("==========================================")
    print(f"candidate_row_count: {summary['row_count']}")
    print(f"distinct_symbols: {summary['symbol_count']}")
    print(f"date_range: {summary['date_min']} .. {summary['date_max']}")
    print("rows_by_source_profile:")
    print(json.dumps(summary["by_source_profile"], indent=2, sort_keys=True))
    print(f"rows_with_spy_context: {summary['with_spy_context']}")
    print(f"rows_missing_spy_context: {summary['missing_spy_context']}")
    print("top_missing_fields:")
    print(json.dumps(summary["top_missing_fields"], indent=2, sort_keys=True))

    if not ns.no_write and candidates:
        ns.output.parent.mkdir(parents=True, exist_ok=True)
        candidates_to_dataframe(candidates).to_csv(ns.output, index=False)
        print(f"wrote: {ns.output.resolve()}")
    elif ns.no_write:
        print("write: skipped (--no-write)")


if __name__ == "__main__":
    main()
