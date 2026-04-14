"""Normalize raw candidate records to canonical ingestion dictionaries."""

from __future__ import annotations

import math

from qops.ingestion.schema import REQUIRED_FIELDS, validate_candidate_schema

_FLOAT_FIELDS = {
    "vrp",
    "vrp_z",
    "gamma_ratio",
    "iv_rank",
    "price",
    "vol_trigger",
    "call_wall",
    "put_wall",
}
_ALLOW_NONE = {"vrp_z", "gamma_ratio", "vol_trigger", "call_wall", "put_wall"}


def _normalize_numeric(value: object, field: str, *, allow_none: bool) -> float | None:
    if value is None:
        if allow_none:
            return None
        raise ValueError(f"{field} must be present")
    if isinstance(value, str):
        raw = value.strip()
        if raw == "":
            if allow_none:
                return None
            raise ValueError(f"{field} must be present")
        try:
            parsed = float(raw)
        except ValueError as exc:
            raise ValueError(f"{field} must be numeric") from exc
        if not math.isfinite(parsed):
            raise ValueError(f"{field} must be finite")
        return parsed
    if isinstance(value, (int, float)):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError(f"{field} must be finite")
        return parsed
    raise ValueError(f"{field} must be numeric")


def normalize_candidate_record(record: dict) -> dict:
    """
    Normalize raw candidate record into canonical form for downstream processing.
    """
    if not isinstance(record, dict):
        raise ValueError("record must be dict")

    missing = [field for field in REQUIRED_FIELDS if field not in record]
    if missing:
        raise ValueError(f"missing required fields: {missing}")

    normalized = dict(record)
    symbol = normalized["symbol"]
    if not isinstance(symbol, str):
        raise ValueError("symbol must be string")
    normalized["symbol"] = symbol.strip()

    confidence_raw = normalized["confidence"]
    if isinstance(confidence_raw, str):
        if confidence_raw.strip() == "":
            raise ValueError("confidence must be int")
        try:
            confidence = int(confidence_raw.strip())
        except ValueError as exc:
            raise ValueError("confidence must be int") from exc
    elif isinstance(confidence_raw, int):
        confidence = confidence_raw
    else:
        raise ValueError("confidence must be int")
    normalized["confidence"] = confidence

    for field in _FLOAT_FIELDS:
        normalized[field] = _normalize_numeric(
            normalized.get(field),
            field,
            allow_none=field in _ALLOW_NONE,
        )

    validate_candidate_schema(normalized)
    return normalized
