"""C13F chain snapshot export tests (offline, no broker or MCP)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from qops.bridge.chain_snapshot_export import (
    chain_output_path,
    extract_unique_symbol_dates,
    filter_chain_strikes_near_atm,
    normalize_chain_df,
    parse_occ_us_option_contract,
    rows_from_raw_option_chain,
)
from qops.bridge.chain_snapshot_models import REQUIRED_CHAIN_COLUMNS


def test_parse_occ_us_option_contract_call() -> None:
    exp, strike, side = parse_occ_us_option_contract("SPY250117C00600000")
    assert exp == "2025-01-17"
    assert strike == 600.0
    assert side == "call"


def test_parse_occ_us_option_contract_put_and_century() -> None:
    exp, strike, side = parse_occ_us_option_contract("AAPL991231P00005000")
    assert exp == "1999-12-31"
    assert strike == 5.0
    assert side == "put"


def test_parse_occ_us_option_contract_rejects_short() -> None:
    with pytest.raises(ValueError, match="too short"):
        parse_occ_us_option_contract("SPY")


def test_chain_output_path_layout(tmp_path: Path) -> None:
    out = chain_output_path(tmp_path / "root", "2026-06-13", "spy")
    assert out == tmp_path / "root" / "2026-06-13" / "SPY.csv"
    assert out.parent.is_dir()


def test_normalize_chain_df_from_aliases() -> None:
    raw = pd.DataFrame(
        [
            {
                "expiry": "2026-06-20",
                "strike_price": 430,
                "type": "C",
                "oi": 100,
            },
            {
                "expiry": "2026-06-20",
                "strike_price": 435,
                "type": "p",
                "oi": None,
            },
        ]
    )
    df = normalize_chain_df(raw)
    assert list(df.columns) == list(REQUIRED_CHAIN_COLUMNS)
    assert df["option_type"].tolist() == ["call", "put"]
    assert df["open_interest"].tolist() == [100, 0]
    assert df.equals(
        df.sort_values(["expiration", "strike", "option_type"]).reset_index(drop=True)
    )


def test_filter_chain_strikes_near_atm() -> None:
    strikes = [400.0, 405.0, 410.0, 415.0, 420.0, 425.0, 430.0]
    rows = []
    for k in strikes:
        rows.append(
            {
                "expiration": "2026-06-20",
                "strike": k,
                "option_type": "call",
                "open_interest": 1,
            }
        )
    df = normalize_chain_df(pd.DataFrame(rows))
    filtered = filter_chain_strikes_near_atm(df, spot_price=424.0, strikes_each_side=1)
    kept = sorted(filtered["strike"].unique().tolist())
    assert kept == [420.0, 425.0, 430.0]


def test_rows_from_raw_option_chain_offline() -> None:
    snapshots = {
        "SPY250620C00430000": {"openInterest": 42},
        "bad": "not a dict",
        "INVALID": {"open_interest": 1},
    }
    rows = rows_from_raw_option_chain(snapshots)
    assert len(rows) == 1
    assert rows[0]["expiration"] == "2025-06-20"
    assert rows[0]["strike"] == 430.0
    assert rows[0]["option_type"] == "call"
    assert rows[0]["open_interest"] == 42


def test_extract_unique_symbol_dates_order() -> None:
    payload = [
        {"symbol": "spy", "trade_date": "2026-06-13", "price": 425.0},
        {"symbol": "SPY", "trade_date": "2026-06-13", "price": 999.0},
        {"symbol": "QQQ", "trade_date": "2026-06-13", "price": 380.0},
    ]
    triples = extract_unique_symbol_dates(payload)
    assert triples == [("2026-06-13", "SPY", 425.0), ("2026-06-13", "QQQ", 380.0)]
