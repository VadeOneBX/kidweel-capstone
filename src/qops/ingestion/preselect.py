"""Deterministic pre-select filters for normalized candidate records."""

from __future__ import annotations


def preselect_candidates(records: list[dict]) -> list[dict]:
    """
    Apply deterministic pre-selection filters to raw normalized candidates.
    """
    selected: list[dict] = []
    for record in records:
        confidence = record.get("confidence")
        if confidence < 4:
            continue

        if record.get("vol_trigger") is None:
            continue

        if record.get("call_wall") is None and record.get("put_wall") is None:
            continue

        vrp_z = record.get("vrp_z")
        if vrp_z is not None and abs(vrp_z) > 3.0:
            continue

        gamma_ratio = record.get("gamma_ratio")
        if gamma_ratio is not None and gamma_ratio > 3.0:
            continue

        selected.append(record)
    return selected
