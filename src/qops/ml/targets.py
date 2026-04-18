from __future__ import annotations

import pandas as pd


def build_expression_target(df: pd.DataFrame) -> pd.Series:
    """Build a binary offline target: 1 if profitable and not stopped out, else 0.

    Args:
        df: Must include ``realized_pnl`` and ``exit_reason``.

    Returns:
        Integer series aligned to ``df`` index.

    Raises:
        ValueError: If required columns are missing.
    """
    if "realized_pnl" not in df.columns or "exit_reason" not in df.columns:
        raise ValueError(
            "training frame must include columns 'realized_pnl' and 'exit_reason'"
        )
    return ((df["realized_pnl"] > 0) & (df["exit_reason"] != "STOP")).astype(int)
