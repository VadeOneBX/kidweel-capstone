from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {
    "trade_date",
    "symbol",
    "source_type",
    "price",
    "vol_trigger",
    "call_wall",
    "put_wall",
    "gamma_ratio",
    "vrp",
    "vrp_z",
    "iv_rank",
    "regime_label",
    "confidence",
    "notes",
}


def load_processed_spotgamma_csv(path: str | Path) -> pd.DataFrame:
    """Load a processed SpotGamma CSV and validate required columns.

    Args:
        path: Path to a ``*.csv`` file under ``data/spotgamma/processed/``.

    Returns:
        The loaded DataFrame.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If any required column is missing.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"processed SpotGamma csv not found: {p}")

    df = pd.read_csv(p)
    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")
    return df
