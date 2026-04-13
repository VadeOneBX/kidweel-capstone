"""Wall proximity classification."""

from __future__ import annotations

import math

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from qops.schemas.environment import WallState


def _relative_distance(price: float, level: float) -> float | None:
    if not math.isfinite(price) or not math.isfinite(level) or price <= 0.0:
        return None
    return abs(price - level) / price


def classify_wall_state(
    price: float,
    call_wall: float | None,
    put_wall: float | None,
    threshold: float,
) -> WallState:
    """
    Classify wall proximity deterministically from price and wall levels.

    Priority:
    missing wall(s) -> UNKNOWN
    near call wall -> NEAR_CALL_WALL
    near put wall -> NEAR_PUT_WALL
    strictly between walls -> BETWEEN_WALLS
    otherwise -> OUTSIDE_WALLS
    """
    if call_wall is None or put_wall is None:
        return WallState.UNKNOWN
    if not math.isfinite(price) or not math.isfinite(threshold) or threshold < 0.0:
        return WallState.UNKNOWN
    if not math.isfinite(call_wall) or not math.isfinite(put_wall):
        return WallState.UNKNOWN

    low = min(put_wall, call_wall)
    high = max(put_wall, call_wall)

    near_call = _relative_distance(price, call_wall)
    near_put = _relative_distance(price, put_wall)
    if near_call is not None and near_call <= threshold:
        return WallState.NEAR_CALL_WALL
    if near_put is not None and near_put <= threshold:
        return WallState.NEAR_PUT_WALL
    if low < price < high:
        return WallState.BETWEEN_WALLS
    return WallState.OUTSIDE_WALLS
