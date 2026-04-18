from __future__ import annotations

from pathlib import Path

import pandas as pd


def append_market_context_row(row: dict, output_csv: str | Path) -> Path:
    """Append one SPY market context row, deduplicating by ``trade_date`` (keep last).

    Args:
        row: Column names must include ``trade_date`` for deduplication.
        output_csv: Destination CSV path (created if missing).

    Returns:
        Resolved path to the written CSV.
    """
    out = Path(output_csv)
    out.parent.mkdir(parents=True, exist_ok=True)

    df_new = pd.DataFrame([row])
    if out.exists():
        df_old = pd.read_csv(out)
        df = pd.concat([df_old, df_new], ignore_index=True)
        df = df.drop_duplicates(subset=["trade_date"], keep="last")
    else:
        df = df_new

    df = df.sort_values("trade_date")
    df.to_csv(out, index=False)
    return out
