"""SPY.xlsx context ingest (separate from scanner exports)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from qops.backtest.spotgamma_replay_builder import build_replay_candidates
from qops.ingest.spotgamma_loader import (
    detect_xlsx_profile,
    is_spy_excel_filename,
    load_scanner_xlsx,
    load_spy_excel,
)
from qops.ingest.spotgamma_normalize import (
    load_session_spy_excel_context,
    load_raw_profile_contexts,
)


def test_spy_excel_filename_detection() -> None:
    assert is_spy_excel_filename("SPY.xlsx")
    assert is_spy_excel_filename(Path("data/raw/2026-06-12/spy.xlsx"))
    assert not is_spy_excel_filename("squeeze.xlsx")


def test_spy_excel_not_detected_as_scanner_profile(tmp_path: Path) -> None:
    cols = ["Trade Date", "Previous Close", "Gamma Ratio", "1 M IV", "1 M RV", "IV Rank"]
    df = pd.DataFrame(
        [{"Trade Date": "2026-06-12", "Previous Close": 100, "Gamma Ratio": 1.0, "1 M IV": 0.2, "1 M RV": 0.15, "IV Rank": 0.3}]
    )
    path = tmp_path / "SPY.xlsx"
    df.to_excel(path, index=False)
    profile = detect_xlsx_profile(list(pd.read_excel(path, header=0).columns), path=path)
    assert profile == "spy_excel"
    with pytest.raises(ValueError, match="not a scanner export"):
        load_scanner_xlsx(path)


def test_invalid_spy_excel_reports_parse_error(tmp_path: Path) -> None:
    session = tmp_path / "raw" / "2026-06-12"
    session.mkdir(parents=True)
    path = session / "SPY.xlsx"
    pd.DataFrame([{"Symbol": "SPY", "Gamma Ratio": 1.0}]).to_excel(path, index=False)
    load = load_session_spy_excel_context(session)
    assert load.parse_error
    assert load.context_rows == ()


def test_spy_excel_rows_do_not_become_candidates(tmp_path: Path) -> None:
    session = tmp_path / "raw" / "2026-06-12"
    session.mkdir(parents=True)
    df = pd.DataFrame(
        [
            {
                "Trade Date": "2026-06-12",
                "Previous Close": 500.0,
                "Gamma Ratio": 1.1,
                "Delta Ratio": -0.5,
                "Put/Call OI Ratio": 1.2,
                "Volume Ratio": 0.9,
                "1 M IV": 0.2,
                "1 M RV": 0.18,
                "IV Rank": 0.4,
                "Skew": -0.1,
                "NE Skew": -0.05,
                "Hedge Wall": 510,
                "Call Wall": 520,
                "Put Wall": 480,
            }
        ]
    )
    df.to_excel(session / "SPY.xlsx", index=False)
    squeeze = pd.DataFrame(
        [
            {
                "Symbol": "AAPL",
                "Current Price": 200,
                "Stock Volume": 1e6,
                "Gamma Ratio": 1.0,
                "Options Impact": 0.5,
            }
        ]
    )
    squeeze.to_excel(session / "squeeze.xlsx", index=False)
    contexts = load_raw_profile_contexts(tmp_path, raw_session_dates=("2026-06-12",))
    candidates = build_replay_candidates(contexts)
    assert len(candidates) == 1
    assert candidates[0].symbol == "AAPL"
    assert candidates[0].has_spy_context is True
    assert candidates[0].spy_gamma_ratio == pytest.approx(1.1)


def test_spy_excel_prefers_over_spy_history_csv_for_same_date(tmp_path: Path) -> None:
    session = tmp_path / "raw" / "2026-06-12"
    session.mkdir(parents=True)
    pd.DataFrame(
        [{"Trade Date": "2026-06-12", "Previous Close": 1, "Gamma Ratio": 9.0, "1 M IV": 0.1, "1 M RV": 0.1, "IV Rank": 0.1}]
    ).to_csv(tmp_path / "raw" / "SPY_history_table.csv", index=False)
    pd.DataFrame(
        [{"Trade Date": "2026-06-12", "Previous Close": 500, "Gamma Ratio": 1.5, "1 M IV": 0.2, "1 M RV": 0.18, "IV Rank": 0.4}]
    ).to_excel(session / "SPY.xlsx", index=False)
    pd.DataFrame(
        [{"Symbol": "AAPL", "Current Price": 1, "Stock Volume": 1, "Gamma Ratio": 1.0, "Options Impact": 1}]
    ).to_excel(session / "squeeze.xlsx", index=False)
    contexts = load_raw_profile_contexts(tmp_path, raw_session_dates=("2026-06-12",))
    cand = build_replay_candidates(contexts)[0]
    assert cand.spy_gamma_ratio == pytest.approx(1.5)


def test_load_spy_excel_minimal(tmp_path: Path) -> None:
    path = tmp_path / "SPY.xlsx"
    pd.DataFrame(
        [{"Trade Date": "2026-06-01", "Previous Close": 1, "Gamma Ratio": 1.0, "1 M IV": 0.2, "1 M RV": 0.1, "IV Rank": 0.3}]
    ).to_excel(path, index=False)
    out = load_spy_excel(path)
    assert out.iloc[0]["source_profile"] == "spy_excel"
