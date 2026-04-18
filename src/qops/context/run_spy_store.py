"""CLI: append latest SPY row from a CSV into the market context store."""

from __future__ import annotations

import argparse

import pandas as pd

from qops.context.market_store import append_market_context_row
from qops.context.spy_store import infer_spy_gamma_regime, load_spy_history


def _optional_float(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return float(value)


def main() -> None:
    """Parse CLI args, take the last SPY history row, and append to the context CSV."""
    parser = argparse.ArgumentParser(description="Append latest SPY row to market context store.")
    parser.add_argument("--spy-csv", required=True, help="Path to incoming SPY CSV (latest row used).")
    parser.add_argument("--output-csv", required=True, help="Path to append-only SPY context store.")
    args = parser.parse_args()

    df = load_spy_history(args.spy_csv)
    if df.empty:
        raise ValueError("empty SPY csv")

    row = df.iloc[-1].to_dict()
    trade_date = row.get("Trade Date") or row.get("trade_date")
    if trade_date is None or (isinstance(trade_date, float) and pd.isna(trade_date)):
        raise ValueError("latest SPY row missing trade_date (expected Trade Date or trade_date)")

    close_raw = row.get("Previous Close") or row.get("close")
    if close_raw is None or (isinstance(close_raw, float) and pd.isna(close_raw)):
        raise ValueError("latest SPY row missing close (expected Previous Close or close)")
    close = float(close_raw)

    vol_raw = row.get("Hedge Wall") or row.get("vol_trigger")
    vol_trigger = None if vol_raw is None or (isinstance(vol_raw, float) and pd.isna(vol_raw)) else float(vol_raw)

    gamma_regime = infer_spy_gamma_regime(close=close, vol_trigger=vol_trigger)

    call_wall = _optional_float(row.get("Call Wall") or row.get("call_wall"))
    put_wall = _optional_float(row.get("Put Wall") or row.get("put_wall"))

    append_market_context_row(
        {
            "trade_date": trade_date,
            "close": close,
            "vol_trigger": vol_trigger,
            "call_wall": call_wall,
            "put_wall": put_wall,
            "gamma_regime": gamma_regime,
            "above_vol_trigger": bool(vol_trigger is not None and close > vol_trigger),
            "note": "",
        },
        args.output_csv,
    )


if __name__ == "__main__":
    main()
