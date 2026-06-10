"""Canonical PMP → Min R/R table (STRUCT-MATH-C1A)."""

from __future__ import annotations

import math

import pytest

from qops.risk.pmp_policy import (
    PMP_TO_MIN_RR,
    min_rr_for_pmp,
    normalize_pmp_bucket,
    passes_pmp_rr_gate,
)


@pytest.mark.parametrize(
    ("pmp", "min_rr"),
    [
        (0.25, 3.00),
        (0.40, 1.50),
        (0.45, 1.22),
        (0.50, 1.00),
        (0.80, 0.25),
        (0.90, 0.11),
    ],
)
def test_table_exact_buckets(pmp: float, min_rr: float) -> None:
    assert min_rr_for_pmp(pmp) == pytest.approx(min_rr)
    assert normalize_pmp_bucket(pmp) == pytest.approx(pmp)


@pytest.mark.parametrize(
    ("raw_pmp", "bucket", "min_rr"),
    [
        (0.47, 0.45, 1.22),
        (0.52, 0.50, 1.00),
        (0.64, 0.60, 0.67),
        (0.89, 0.85, 0.18),
    ],
)
def test_floor_to_nearest_five_percent_bucket(raw_pmp: float, bucket: float, min_rr: float) -> None:
    assert normalize_pmp_bucket(raw_pmp) == pytest.approx(bucket)
    assert min_rr_for_pmp(raw_pmp) == pytest.approx(min_rr)


def test_pmp_below_table_range_fails_closed() -> None:
    with pytest.raises(ValueError, match="supported table range"):
        normalize_pmp_bucket(0.24)
    assert passes_pmp_rr_gate(0.24, 5.0) is False


def test_pmp_above_table_range_fails_closed() -> None:
    with pytest.raises(ValueError, match="supported table range"):
        normalize_pmp_bucket(0.91)
    assert passes_pmp_rr_gate(0.91, 5.0) is False


@pytest.mark.parametrize("bad_p", [0.0, 1.0, -0.1, math.nan])
def test_pmp_open_interval_fails_closed(bad_p: float) -> None:
    with pytest.raises(ValueError):
        normalize_pmp_bucket(bad_p)
    assert passes_pmp_rr_gate(bad_p, 1.5) is False


def test_rr_below_table_requirement_fails() -> None:
    assert passes_pmp_rr_gate(0.40, 1.49) is False
    assert passes_pmp_rr_gate(0.45, 1.21) is False


def test_rr_equal_to_table_requirement_passes() -> None:
    assert passes_pmp_rr_gate(0.40, 1.50) is True
    assert passes_pmp_rr_gate(0.45, 1.22) is True
    assert passes_pmp_rr_gate(0.50, 1.00) is True


def test_canonical_table_keys() -> None:
    assert len(PMP_TO_MIN_RR) == 14
    assert min(PMP_TO_MIN_RR) == pytest.approx(0.25)
    assert max(PMP_TO_MIN_RR) == pytest.approx(0.90)
