"""Skew classification from wing implied volatilities."""

from __future__ import annotations

import math

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from qops.schemas.environment import SkewState


def classify_skew_state(
    put_wing_iv: float,
    call_wing_iv: float,
    neutral_band: float,
) -> SkewState:
    """
    Classify skew using put-wing IV minus call-wing IV.

    skew = put_wing_iv - call_wing_iv
    abs(skew) < neutral_band -> NEUTRAL
    skew > neutral_band -> PUTS_RICH
    skew < -neutral_band -> CALLS_RICH
    """
    if not math.isfinite(put_wing_iv) or not math.isfinite(call_wing_iv) or not math.isfinite(neutral_band):
        return SkewState.NEUTRAL
    if neutral_band < 0.0:
        return SkewState.NEUTRAL
    skew = put_wing_iv - call_wing_iv
    if abs(skew) < neutral_band:
        return SkewState.NEUTRAL
    if skew > neutral_band:
        return SkewState.PUTS_RICH
    return SkewState.CALLS_RICH
