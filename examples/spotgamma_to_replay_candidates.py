#!/usr/bin/env python3
"""Stage SpotGamma replay candidates from context corpus (SG-BT-C2 / C2A).

Canonical flow:
  PYTHONPATH=src python examples/spotgamma_replay_corpus.py --include-raw
  PYTHONPATH=src python examples/spotgamma_to_replay_candidates.py \\
    --input data/processed/spotgamma_context_sample.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from qops.backtest.spotgamma_replay_builder import (
    STALE_CONTEXT_CSV_MESSAGE,
    assess_context_csv_freshness,
    build_replay_candidates,
    candidates_to_dataframe,
    load_contexts,
    load_contexts_from_csv,
    rebuild_fresh_context,
    summarize_replay_candidates,
)


def _resolve_contexts(
    *,
    input_path: Path,
    spotgamma_root: Path,
    include_raw: bool,
    allow_stale_input: bool,
    rebuild_if_stale: bool,
    raw_session_dates: tuple[str, ...] | None,
    raw_only: bool,
) -> tuple[list, str]:
    """Return (contexts, context_source_label)."""
    if input_path.is_file():
        freshness = assess_context_csv_freshness(input_path)
        if not freshness.is_fresh:
            if rebuild_if_stale:
                print(
                    f"Note: {STALE_CONTEXT_CSV_MESSAGE}",
                    file=sys.stderr,
                )
                print(
                    "Rebuilding fresh context via ingest (--include-raw).",
                    file=sys.stderr,
                )
                return rebuild_fresh_context(
                    spotgamma_root,
                    raw_session_dates=raw_session_dates,
                    include_processed_weekly=not raw_only,
                ), "ingest_rebuild"
            if allow_stale_input:
                print(f"WARNING: {STALE_CONTEXT_CSV_MESSAGE}", file=sys.stderr)
                print(
                    "Continuing with --allow-stale-input (diagnostics only; degraded candidates).",
                    file=sys.stderr,
                )
                return load_contexts_from_csv(input_path), "stale_csv"
            raise SystemExit(STALE_CONTEXT_CSV_MESSAGE)
        return load_contexts_from_csv(input_path), "fresh_csv"

    if include_raw:
        return rebuild_fresh_context(
            spotgamma_root,
            raw_session_dates=raw_session_dates,
            include_processed_weekly=not raw_only,
        ), "ingest_rebuild"
    raise SystemExit(
        f"Input not found: {input_path}. "
        "Re-run spotgamma_replay_corpus.py --include-raw or pass --include-raw here."
    )


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="SpotGamma context → replay candidate staging")
    p.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/spotgamma_context_sample.csv"),
        help="Normalized context CSV (must be post-C1A fresh unless overridden)",
    )
    p.add_argument(
        "--spotgamma-root",
        type=Path,
        default=Path("data/spotgamma"),
        help="SpotGamma root for ingest rebuild",
    )
    p.add_argument(
        "--include-raw",
        action="store_true",
        help="Rebuild context from ingest when --input is missing",
    )
    p.add_argument(
        "--allow-stale-input",
        action="store_true",
        help="Diagnostics only: accept pre-C1A context CSV (degraded candidates)",
    )
    p.add_argument(
        "--rebuild-if-stale",
        action="store_true",
        help="If --input is stale, rebuild fresh context via ingest (--include-raw)",
    )
    p.add_argument(
        "--raw-session-date",
        action="append",
        default=[],
        metavar="YYYY-MM-DD",
        help="Limit raw ingest to session folder(s) under raw/ (repeatable)",
    )
    p.add_argument(
        "--raw-only",
        action="store_true",
        help="With rebuild/include-raw, skip processed weekly CSVs",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/spotgamma_replay_candidates.csv"),
    )
    p.add_argument("--no-write", action="store_true")
    ns = p.parse_args(argv)

    raw_dates = tuple(ns.raw_session_date) if ns.raw_session_date else None
    contexts, source = _resolve_contexts(
        input_path=ns.input,
        spotgamma_root=ns.spotgamma_root,
        include_raw=ns.include_raw,
        allow_stale_input=ns.allow_stale_input,
        rebuild_if_stale=ns.rebuild_if_stale,
        raw_session_dates=raw_dates,
        raw_only=ns.raw_only,
    )
    candidates = build_replay_candidates(contexts)
    summary = summarize_replay_candidates(candidates)

    print("SpotGamma replay candidates (staging only)")
    print("==========================================")
    print(f"context_source: {source}")
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
