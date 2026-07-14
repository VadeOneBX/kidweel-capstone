"""Full daily scanner headers must map for squeeze / vrp / reverse-vrp."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from qops.ingest.spotgamma_loader import (
    _SCANNER_HEADERS,
    detect_xlsx_profile,
    load_scanner_xlsx,
    normalize_header_label,
)
from qops.ingest.spotgamma_normalize import (
    context_from_squeeze_row,
    context_from_vrp_row,
)
from qops.backtest.spotgamma_replay_builder import build_replay_candidates


_FULL_HEADERS = [
    "Symbol",
    "Current Price",
    "Previous Close",
    "Stock Volume",
    "52 Week High",
    "52 Week Low",
    "Earnings Date",
    "Key Gamma Strike",
    "Key Delta Strike",
    "Hedge Wall",
    "Call Wall",
    "Put Wall",
    "Options Impact",
    "Call Gamma",
    "Put Gamma",
    "Next Exp Gamma",
    "Next Exp Delta",
    "Top Gamma Exp",
    "Top Delta Exp",
    "Call Volume",
    "Put Volume",
    "Next Exp Call Vol",
    "Next Exp Put Vol",
    "Put/Call OI\xa0Ratio",
    "Volume Ratio",
    "Gamma Ratio",
    "Delta Ratio",
    "NE Skew",
    "Skew",
    "1 M RV",
    "1 M IV",
    "IV Rank",
    "Garch Rank",
    "Skew Rank",
    "Options Implied Move",
    "DPI",
    "% DPI Volume",
    "5 day DPI",
    "5d % DPI Volume",
]


def _full_row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "Symbol": "ONDS",
        "Current Price": 7.27,
        "Previous Close": 7.27,
        "Stock Volume": 49135652,
        "52 Week High": 15.28,
        "52 Week Low": 1.78,
        "Earnings Date": None,
        "Key Gamma Strike": 7.0,
        "Key Delta Strike": 15.0,
        "Hedge Wall": 7.5,
        "Call Wall": 10.0,
        "Put Wall": 7.0,
        "Options Impact": 17.43,
        "Call Gamma": -55332588,
        "Put Gamma": -39179975,
        "Next Exp Gamma": 0.3613,
        "Next Exp Delta": 2.2537,
        "Top Gamma Exp": "2026-07-17",
        "Top Delta Exp": "2027-01-15",
        "Call Volume": 72480,
        "Put Volume": 44478,
        "Next Exp Call Vol": 0.288,
        "Next Exp Put Vol": 0.6054,
        "Put/Call OI\xa0Ratio": 0.4626,
        "Volume Ratio": 0.6137,
        "Gamma Ratio": 1.4123,
        "Delta Ratio": -1.1388,
        "NE Skew": 0.0173,
        "Skew": 0.0615,
        "1 M RV": 0.7005,
        "1 M IV": 0.8937,
        "IV Rank": 0.076,
        "Garch Rank": 0.0719,
        "Skew Rank": 0.392,
        "Options Implied Move": 0.4101,
        "DPI": 50.66,
        "% DPI Volume": 0.7798,
        "5 day DPI": 0.4598,
        "5d % DPI Volume": 0.73824,
    }
    base.update(overrides)
    return base


def test_scanner_headers_cover_full_daily_schema() -> None:
    for label in _FULL_HEADERS:
        key = normalize_header_label(label)
        assert key in _SCANNER_HEADERS, f"missing map for {label!r} ({key})"


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("2026-07-13_squeeze.xlsx", "squeeze"),
        ("squeeze.xlsx", "squeeze"),
        ("2026-07-13_reverse_vrp.xlsx", "reverse_vrp"),
        ("reverse-vrp.xlsx", "reverse_vrp"),
        ("2026-07-13_vrp.xlsx", "vrp"),
        ("vrp.xlsx", "vrp"),
    ],
)
def test_full_schema_profile_detection_follows_filename(tmp_path: Path, filename: str, expected: str) -> None:
    path = tmp_path / filename
    pd.DataFrame([_full_row()]).to_excel(path, index=False)
    profile = detect_xlsx_profile(list(pd.read_excel(path, header=0).columns), path=path)
    assert profile == expected


def test_load_full_squeeze_maps_key_levels(tmp_path: Path) -> None:
    path = tmp_path / "2026-07-13_squeeze.xlsx"
    pd.DataFrame([_full_row()]).to_excel(path, index=False)
    df, profile = load_scanner_xlsx(path)
    assert profile == "squeeze"
    row = df.iloc[0]
    assert float(row["gamma_ratio"]) == pytest.approx(1.4123)
    assert float(row["delta_ratio"]) == pytest.approx(-1.1388)
    assert float(row["call_wall"]) == pytest.approx(10.0)
    assert float(row["put_wall"]) == pytest.approx(7.0)
    assert float(row["hedge_wall"]) == pytest.approx(7.5)
    assert float(row["one_month_iv"]) == pytest.approx(0.8937)
    assert float(row["iv_rank"]) == pytest.approx(0.076)
    assert float(row["put_call_oi_ratio"]) == pytest.approx(0.4626)
    assert "Gamma Ratio" not in df.columns

    ctx = context_from_squeeze_row(row, session_date="2026-07-13")
    assert ctx.source_profile == "squeeze"
    assert ctx.gamma_ratio == pytest.approx(1.4123)
    assert ctx.iv_rank == pytest.approx(0.076)
    assert ctx.vrp == pytest.approx(0.8937 - 0.7005)
    cand = build_replay_candidates([ctx])[0]
    assert cand.call_wall == pytest.approx(10.0)
    assert cand.delta_ratio == pytest.approx(-1.1388)


def test_load_full_reverse_vrp_maps_gamma_and_walls(tmp_path: Path) -> None:
    path = tmp_path / "2026-07-13_reverse_vrp.xlsx"
    pd.DataFrame([_full_row(Symbol="ETHA", **{"Gamma Ratio": 1.8944})]).to_excel(path, index=False)
    df, profile = load_scanner_xlsx(path)
    assert profile == "reverse_vrp"
    row = df.iloc[0]
    ctx = context_from_vrp_row(row, profile=profile, session_date="2026-07-13")
    assert ctx.gamma_ratio == pytest.approx(1.8944)
    cand = build_replay_candidates([ctx])[0]
    assert cand.gamma_ratio == pytest.approx(1.8944)
    assert cand.call_wall == pytest.approx(10.0)


def test_thin_legacy_vrp_still_loads(tmp_path: Path) -> None:
    path = tmp_path / "vrp.xlsx"
    thin = pd.DataFrame(
        [
            {
                "Symbol": "SLS",
                "Current Price": 12.93,
                "Earnings Date": None,
                "Key Gamma Strike": 14.0,
                "Key Delta Strike": 5.0,
                "Hedge Wall": 1.0,
                "Call Wall": 15.0,
                "Put Wall": 6.0,
                "Options Impact": 8.4,
                "NE Skew": 0.06,
                "Skew": -0.97,
                "1 M RV": 1.33,
                "1 M IV": 2.28,
                "IV Rank": 0.97,
                "Garch Rank": 0.45,
                "Options Implied Move": 1.95,
            }
        ]
    )
    thin.to_excel(path, index=False)
    df, profile = load_scanner_xlsx(path)
    assert profile == "vrp"
    assert "gamma_ratio" not in df.columns or pd.isna(df.iloc[0].get("gamma_ratio"))
    ctx = context_from_vrp_row(df.iloc[0], profile=profile, session_date="2026-07-10")
    assert ctx.gamma_ratio is None
    assert ctx.vrp == pytest.approx(2.28 - 1.33)
