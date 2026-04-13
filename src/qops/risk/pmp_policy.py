"""Deterministic PMP policy math."""

from __future__ import annotations

import math


def validate_pmp(pmp: float) -> None:
    """Raise clear errors if PMP is invalid."""
    if not math.isfinite(pmp):
        raise ValueError("pmp must be finite")
    if not (0.0 < pmp < 1.0):
        raise ValueError("pmp must satisfy 0 < pmp < 1")


def required_rr_from_pmp(pmp: float) -> float:
    """
    Return minimum required reward/risk using: (1 - pmp) / pmp.

    pmp must be a decimal in the open interval (0, 1).
    """
    validate_pmp(pmp)
    return (1.0 - pmp) / pmp
