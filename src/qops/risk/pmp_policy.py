"""Deterministic PMP policy math (Option Alpha canonical Min R/R table)."""

from __future__ import annotations

import math

# Canonical PMP → minimum reward/risk (decimal RR, not percent labels).
PMP_TO_MIN_RR: dict[float, float] = {
    0.25: 3.00,
    0.30: 2.33,
    0.35: 1.86,
    0.40: 1.50,
    0.45: 1.22,
    0.50: 1.00,
    0.55: 0.82,
    0.60: 0.67,
    0.65: 0.54,
    0.70: 0.43,
    0.75: 0.33,
    0.80: 0.25,
    0.85: 0.18,
    0.90: 0.11,
}

_SUPPORTED_PMP_BUCKETS: tuple[float, ...] = tuple(sorted(PMP_TO_MIN_RR.keys()))
_MIN_TABLE_PMP = _SUPPORTED_PMP_BUCKETS[0]
_MAX_TABLE_PMP = _SUPPORTED_PMP_BUCKETS[-1]


def validate_pmp(pmp: float) -> None:
    """Raise clear errors if PMP is invalid (open unit interval)."""
    if not math.isfinite(pmp):
        raise ValueError("pmp must be finite")
    if not (0.0 < pmp < 1.0):
        raise ValueError("pmp must satisfy 0 < pmp < 1")


def normalize_pmp_bucket(pmp: float) -> float:
    """
    Map raw PMP to a supported table bucket.

    Uses floor-to-nearest 5% bucket within 0.25–0.90 (never round up).
    PMP outside the table range fails closed.
    """
    validate_pmp(pmp)
    if pmp < _MIN_TABLE_PMP or pmp > _MAX_TABLE_PMP:
        raise ValueError("pmp must be within supported table range 0.25-0.90")
    bucket = math.floor(pmp * 20.0 + 1e-12) / 20.0
    if bucket not in PMP_TO_MIN_RR:
        raise ValueError("pmp does not map to a supported table bucket")
    return bucket


def min_rr_for_pmp(pmp: float) -> float:
    """Return minimum required reward/risk for raw PMP using the canonical table."""
    bucket = normalize_pmp_bucket(pmp)
    return PMP_TO_MIN_RR[bucket]


def passes_pmp_rr_gate(pmp: float, reward_risk: float) -> bool:
    """Return whether reward_risk clears the table requirement for PMP (fail closed on invalid inputs)."""
    if not math.isfinite(reward_risk) or reward_risk <= 0.0:
        return False
    try:
        required = min_rr_for_pmp(pmp)
    except ValueError:
        return False
    return reward_risk >= required


def required_rr_from_pmp(pmp: float) -> float:
    """Return minimum required reward/risk from the canonical PMP table (bucketed, conservative floor)."""
    return min_rr_for_pmp(pmp)
