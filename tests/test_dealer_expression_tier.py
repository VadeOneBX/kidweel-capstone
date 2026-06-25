"""Dealer-weighted expression tier mapping (STRUCT-C2A slice 3)."""

from __future__ import annotations

import pytest

from qops.strategy.dealer_expression_tier import dealer_tier_for_score


@pytest.mark.parametrize(
    ("score", "tier", "rr", "pmp_max"),
    [
        (12, "A", 1.05, 0.55),
        (10, "A", 1.05, 0.55),
        (9, "B", 1.15, 0.52),
        (8, "B", 1.15, 0.52),
        (7, "C", 1.25, 0.48),
        (6, "C", 1.25, 0.48),
        (5, "D", 1.40, 0.45),
        (4, "D", 1.40, 0.45),
        (3, "E", 1.50, 0.42),
        (0, "E", 1.50, 0.42),
    ],
)
def test_dealer_tier_for_score_maps_table(score: int, tier: str, rr: float, pmp_max: float) -> None:
    gate = dealer_tier_for_score(score)
    assert gate.tier == tier
    assert gate.rr_dealer_required == rr
    assert gate.pmp_dealer_max == pmp_max
