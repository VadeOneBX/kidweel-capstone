"""IV rank classification."""

from __future__ import annotations

import math

from qops.environment.constants import IV_CHEAP_MAX, IV_EXPENSIVE_MIN

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from qops.schemas.environment import IVState


def classify_iv_state(iv_rank: float) -> IVState:
    """
    Classify IV rank into CHEAP_VOL, MID_VOL, or EXPENSIVE_VOL.

    iv_rank < IV_CHEAP_MAX -> CHEAP_VOL
    IV_CHEAP_MAX <= iv_rank < IV_EXPENSIVE_MIN -> MID_VOL
    iv_rank >= IV_EXPENSIVE_MIN -> EXPENSIVE_VOL
    """
    if not math.isfinite(iv_rank):
        return IVState.MID_VOL
    if iv_rank < IV_CHEAP_MAX:
        return IVState.CHEAP_VOL
    if iv_rank < IV_EXPENSIVE_MIN:
        return IVState.MID_VOL
    return IVState.EXPENSIVE_VOL
