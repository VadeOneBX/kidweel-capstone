"""Raw weekly candidate schema validation."""

from __future__ import annotations

import math

REQUIRED_FIELDS = [
    "symbol",
    "regime_label",
    "confidence",
    "vrp",
    "vrp_z",
    "gamma_ratio",
    "iv_rank",
    "price",
    "vol_trigger",
    "call_wall",
    "put_wall",
]

OPTIONAL_FIELDS = [
    "squeeze_score",
    "implied_move",
    "reasons",
]

_ALLOW_NONE_NUMERIC = {"vrp_z", "gamma_ratio", "vol_trigger", "call_wall", "put_wall"}
_NUMERIC_FIELDS = {
    "vrp",
    "vrp_z",
    "gamma_ratio",
    "iv_rank",
    "price",
    "vol_trigger",
    "call_wall",
    "put_wall",
}


def validate_candidate_schema(record: dict) -> None:
    """
    Raise ValueError if required fields are missing or invalid.
    """
    if not isinstance(record, dict):
        raise ValueError("record must be a dict")

    missing = [field for field in REQUIRED_FIELDS if field not in record]
    if missing:
        raise ValueError(f"missing required fields: {missing}")

    symbol = record["symbol"]
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol must be a non-empty string")

    confidence = record["confidence"]
    if not isinstance(confidence, int):
        raise ValueError("confidence must be int")
    if confidence < 0 or confidence > 10:
        raise ValueError("confidence must be between 0 and 10")

    for field in _NUMERIC_FIELDS:
        value = record[field]
        if value is None:
            if field in _ALLOW_NONE_NUMERIC:
                continue
            raise ValueError(f"{field} must be finite numeric")
        if not isinstance(value, (int, float)):
            raise ValueError(f"{field} must be numeric")
        if not math.isfinite(float(value)):
            raise ValueError(f"{field} must be finite")
