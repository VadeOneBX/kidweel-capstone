#!/usr/bin/env python3
"""Build SpotGamma replay corpus context table (SG-BT-C1).

Run:
  PYTHONPATH=src python examples/spotgamma_replay_corpus.py
  PYTHONPATH=src python examples/spotgamma_replay_corpus.py --include-raw --default-confidence 0.0
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qops.ingest.spotgamma_normalize import (
    build_context_corpus,
    contexts_to_dataframe,
    count_by_source_profile,
    missing_field_summary,
    summarize_corpus,
)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="SpotGamma replay corpus context builder")
    p.add_argument(
        "--spotgamma-root",
        type=Path,
        default=Path("data/spotgamma"),
        help="Root with raw/ and processed/ SpotGamma artifacts",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/spotgamma_context_sample.csv"),
        help="Normalized context sample CSV (under data/, gitignored)",
    )
    p.add_argument(
        "--include-raw",
        action="store_true",
        help="Also ingest raw profile exports (SPY history CSV + scanner XLSX)",
    )
    p.add_argument(
        "--default-confidence",
        type=float,
        default=None,
        help="Unused for profile-based raw ingest (legacy weekly CLI only)",
    )
    p.add_argument(
        "--no-write",
        action="store_true",
        help="Print summary only; do not write CSV",
    )
    ns = p.parse_args(argv)

    contexts = build_context_corpus(
        ns.spotgamma_root,
        include_raw=ns.include_raw,
        default_confidence_for_raw=ns.default_confidence,
    )
    summary = summarize_corpus(contexts)
    missing = missing_field_summary(contexts)
    by_profile = count_by_source_profile(contexts)

    print("SpotGamma replay corpus (context staging)")
    print("========================================")
    print(f"row_count: {summary['row_count']}")
    print(f"symbol_count: {summary['symbol_count']}")
    print(f"date_range: {summary['date_min']} .. {summary['date_max']}")
    print("rows_by_source_profile:")
    print(json.dumps(by_profile, indent=2, sort_keys=True))
    print("missing_field_summary:")
    print(json.dumps(missing, indent=2, sort_keys=True))
    print(f"spy_history_loaded: {by_profile.get('spy_history', 0) > 0}")
    print(f"squeeze_loaded: {by_profile.get('squeeze', 0) > 0}")
    print(f"vrp_loaded: {by_profile.get('vrp', 0) > 0}")
    print(f"reverse_vrp_loaded: {by_profile.get('reverse_vrp', 0) > 0}")

    wrote = False
    if not ns.no_write and contexts:
        ns.output.parent.mkdir(parents=True, exist_ok=True)
        df = contexts_to_dataframe(contexts)
        df.to_csv(ns.output, index=False)
        wrote = True
        print(f"wrote: {ns.output.resolve()}")
    elif ns.no_write:
        print("write: skipped (--no-write)")
    else:
        print("write: skipped (empty corpus)")

    print(f"data_output_written: {wrote}")


if __name__ == "__main__":
    main()
