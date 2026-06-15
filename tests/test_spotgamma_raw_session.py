"""Raw session scoping for SpotGamma ingest."""

from __future__ import annotations

from pathlib import Path

import pytest

from qops.ingest.spotgamma_normalize import build_context_corpus, load_raw_profile_contexts


pytestmark = pytest.mark.skipif(
    not (Path("data/spotgamma/raw/2026-06-12").is_dir()),
    reason="local raw session fixture not present",
)


def test_raw_session_date_loads_all_scanner_rows_for_2026_06_12() -> None:
    rows = load_raw_profile_contexts(
        "data/spotgamma",
        raw_session_dates=("2026-06-12",),
    )
    from qops.ingest.spotgamma_normalize import split_scanner_and_spy_contexts

    scanner_rows, spy_rows = split_scanner_and_spy_contexts(rows)
    assert len(scanner_rows) == 57
    profiles = {r.source_profile for r in scanner_rows}
    assert profiles == {"squeeze", "vrp", "reverse_vrp"}
    assert all(r.trade_date == "2026-06-12" for r in scanner_rows)
    assert len(spy_rows) >= 1
    assert {r.source_profile for r in spy_rows} <= {"spy_excel", "spy_history"}


def test_spy_excel_attaches_to_replay_candidates_for_2026_06_12() -> None:
    from qops.backtest.spotgamma_replay_builder import build_replay_candidates, summarize_replay_candidates
    from qops.ingest.spotgamma_normalize import build_context_corpus

    ctx = build_context_corpus(
        "data/spotgamma",
        include_raw=True,
        raw_session_dates=("2026-06-12",),
        include_processed_weekly=False,
    )
    summary = summarize_replay_candidates(build_replay_candidates(ctx))
    assert summary["row_count"] == 57
    assert summary["with_spy_context"] == 57
    assert summary["missing_spy_context"] == 0


def test_build_context_corpus_raw_only_session() -> None:
    from qops.ingest.spotgamma_normalize import split_scanner_and_spy_contexts

    ctx = build_context_corpus(
        "data/spotgamma",
        include_raw=True,
        raw_session_dates=("2026-06-12",),
        include_processed_weekly=False,
    )
    scanner_rows, _ = split_scanner_and_spy_contexts(ctx)
    assert len(scanner_rows) == 57
    assert len({c.symbol for c in scanner_rows}) == 50
