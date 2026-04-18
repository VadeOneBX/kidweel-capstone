from __future__ import annotations

import pandas as pd

FEATURE_COLUMNS = [
    "confidence",
    "price",
    "gamma_ratio",
    "vrp_z",
    "iv_rank",
    "spy_above_vol_trigger",
    "chain_highest_oi_strike",
    "chain_concentration_near_spot",
]


def features_to_frame(rows: list[dict]) -> pd.DataFrame:
    """Materialize training matrix columns, filling missing keys with 0.0.

    Args:
        rows: One dict per observation (must include or tolerate missing ``FEATURE_COLUMNS``).

    Returns:
        DataFrame with exactly ``FEATURE_COLUMNS``, numeric dtype suitable for sklearn.
    """
    df = pd.DataFrame(rows).copy()
    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0
    return df[FEATURE_COLUMNS].fillna(0.0)
