#!/usr/bin/env python3
"""Populate replay candidates from one raw session folder (all scanner rows).

Example (2026-06-12 session — squeeze + vrp + reverse-vrp xlsx, no row cap):

  PYTHONPATH=src python examples/populate_raw_session_candidates.py \\
    --raw-session-date 2026-06-12 --no-write

Writes context + replay candidate CSVs unless --no-write.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from qops.backtest.spotgamma_replay_builder import (
    build_replay_candidates,
    candidates_to_dataframe,
    rebuild_fresh_context,
    summarize_replay_candidates,
)
from qops.ingest.spotgamma_normalize import (
    count_by_source_profile,
    contexts_to_dataframe,
    load_session_spy_excel_context,
    resolve_spy_context_source,
    split_scanner_and_spy_contexts,
)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description="Ingest full raw session scanners → context → replay candidates"
    )
    p.add_argument(
        "--spotgamma-root",
        type=Path,
        default=Path("data/spotgamma"),
    )
    p.add_argument(
        "--raw-session-date",
        type=str,
        required=True,
        metavar="YYYY-MM-DD",
        help="Session folder name under data/spotgamma/raw/",
    )
    p.add_argument(
        "--context-output",
        type=Path,
        default=None,
        help="Default: data/processed/spotgamma_context_<date>.csv",
    )
    p.add_argument(
        "--candidates-output",
        type=Path,
        default=None,
        help="Default: data/processed/spotgamma_replay_candidates_<date>.csv",
    )
    p.add_argument("--no-write", action="store_true")
    ns = p.parse_args(argv)

    session = ns.raw_session_date.strip()
    raw_dir = ns.spotgamma_root / "raw" / session
    if not raw_dir.is_dir():
        raise SystemExit(f"Raw session directory not found: {raw_dir.resolve()}")

    contexts = rebuild_fresh_context(
        ns.spotgamma_root,
        raw_session_dates=(session,),
        include_processed_weekly=False,
    )
    scanner_contexts, spy_contexts = split_scanner_and_spy_contexts(contexts)
    spy_load = load_session_spy_excel_context(raw_dir)
    candidates = build_replay_candidates(contexts)
    summary = summarize_replay_candidates(candidates)
    profile_counts = count_by_source_profile(contexts)

    ctx_out = ns.context_output or Path(f"data/processed/spotgamma_context_{session}.csv")
    cand_out = ns.candidates_output or Path(
        f"data/processed/spotgamma_replay_candidates_{session}.csv"
    )

    print("Raw session candidate populate")
    print("============================")
    print(f"raw_session_dir: {raw_dir.resolve()}")
    print(f"scanner_context_rows: {len(scanner_contexts)}")
    print(f"spy_context_source: {resolve_spy_context_source(contexts)}")
    if spy_load.path:
        print(f"spy_excel_path: {spy_load.path}")
    if spy_load.parse_error:
        print(f"spy_excel_parse_error: {spy_load.parse_error}")
    print(f"spy_context_rows: {len(spy_contexts)}")
    print(f"context_rows: {len(contexts)}")
    print(f"replay_candidates: {summary['row_count']}")
    print(f"distinct_symbols: {summary['symbol_count']}")
    print(f"date_range: {summary['date_min']} .. {summary['date_max']}")
    print("source_profile counts:")
    print(json.dumps(profile_counts, indent=2, sort_keys=True))
    print("replay_candidates_by_source_profile:")
    print(json.dumps(summary["by_source_profile"], indent=2, sort_keys=True))
    print(f"candidates_with_spy_context: {summary['with_spy_context']}")
    print(f"candidates_missing_spy_context: {summary['missing_spy_context']}")
    if summary["row_count"] == 0:
        print(
            "note: no candidates — check squeeze.xlsx / vrp.xlsx / reverse-vrp.xlsx in session dir",
            file=sys.stderr,
        )

    if not ns.no_write and contexts:
        ctx_out.parent.mkdir(parents=True, exist_ok=True)
        contexts_to_dataframe(contexts).to_csv(ctx_out, index=False)
        print(f"wrote: {ctx_out.resolve()}")
    if not ns.no_write and candidates:
        cand_out.parent.mkdir(parents=True, exist_ok=True)
        candidates_to_dataframe(candidates).to_csv(cand_out, index=False)
        print(f"wrote: {cand_out.resolve()}")
    elif ns.no_write:
        print("write: skipped (--no-write)")


if __name__ == "__main__":
    main()
