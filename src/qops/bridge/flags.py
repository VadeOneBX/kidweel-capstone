from __future__ import annotations

import pandas as pd

from qops.bridge.models import CandidateFlags


def _near_level(price: float, level: float | None, threshold: float = 0.01) -> bool:
    if level is None or pd.isna(level):
        return False
    if price <= 0:
        return False
    return abs(price - float(level)) / price <= threshold


def build_candidate_flags(
    *,
    row: dict,
    cross_file_overlap: bool,
) -> CandidateFlags:
    """Derive deterministic flags from a SpotGamma row and overlap metadata.

    Args:
        row: One row as a mapping (e.g. ``Series.to_dict()``).
        cross_file_overlap: True if this ``(trade_date, symbol)`` appears in more
            than one ``source_type`` in the loaded frame.

    Returns:
        ``CandidateFlags`` for enrichment payloads (no LLM use).
    """
    price = float(row["price"])
    call_wall = row.get("call_wall")
    put_wall = row.get("put_wall")
    vol_trigger = row.get("vol_trigger")

    inverted_wall = False
    if call_wall is not None and put_wall is not None:
        try:
            inverted_wall = float(put_wall) > float(call_wall)
        except Exception:
            inverted_wall = False

    vol_trigger_breach = False
    if vol_trigger is not None and not pd.isna(vol_trigger):
        vol_trigger_breach = price < float(vol_trigger)

    return CandidateFlags(
        near_call_wall=_near_level(price, call_wall),
        near_put_wall=_near_level(price, put_wall),
        inverted_wall=inverted_wall,
        vol_trigger_breach=vol_trigger_breach,
        cross_file_overlap=bool(cross_file_overlap),
    )
