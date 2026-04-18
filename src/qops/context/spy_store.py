from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_spy_history(csv_path: str | Path) -> pd.DataFrame:
    """Load SPY history from a CSV file.

    Args:
        csv_path: Path to the CSV.

    Returns:
        DataFrame of SPY rows.

    Raises:
        FileNotFoundError: If ``csv_path`` does not exist or is not a file.
    """
    p = Path(csv_path)
    if not p.is_file():
        raise FileNotFoundError(f"SPY history not found: {p}")
    return pd.read_csv(p)


def infer_spy_gamma_regime(close: float, vol_trigger: float | None) -> str:
    """Infer a coarse gamma regime label from spot vs vol trigger (SPY backdrop only).

    Args:
        close: Underlying close.
        vol_trigger: Hedge / vol trigger level, or ``None`` if unknown.

    Returns:
        ``POSITIVE_GAMMA``, ``NEGATIVE_GAMMA``, ``TRANSITION``, or ``UNKNOWN``.
    """
    if vol_trigger is None:
        return "UNKNOWN"
    if close > vol_trigger:
        return "POSITIVE_GAMMA"
    if close < vol_trigger:
        return "NEGATIVE_GAMMA"
    return "TRANSITION"
