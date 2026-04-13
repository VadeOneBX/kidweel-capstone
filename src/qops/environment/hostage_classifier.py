"""Hostage / pinning classification relative to walls."""

from __future__ import annotations

import math

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from qops.schemas.environment import HostageState


def _relative_distance(price: float, level: float) -> float | None:
    if not math.isfinite(price) or not math.isfinite(level) or price <= 0.0:
        return None
    return abs(price - level) / price


def classify_hostage_state(
    price: float,
    call_wall: float | None,
    put_wall: float | None,
    threshold: float,
) -> HostageState:
    """
    Classify hostage state from price relative to call/put walls.

    Priority:
    missing data -> UNKNOWN
    price > call_wall -> ESCAPE_UP
    price < put_wall -> ESCAPE_DOWN
    near either wall -> PINNED
    between walls, closer to call -> PULL_TO_CALL_WALL
    between walls, closer to put -> PULL_TO_PUT_WALL
    otherwise -> NEUTRAL
    """
    if call_wall is None or put_wall is None:
        return HostageState.UNKNOWN
    if not math.isfinite(price) or not math.isfinite(threshold) or threshold < 0.0:
        return HostageState.UNKNOWN
    if not math.isfinite(call_wall) or not math.isfinite(put_wall):
        return HostageState.UNKNOWN

    low = min(put_wall, call_wall)
    high = max(put_wall, call_wall)

    # ESCAPE checks must come after all isfinite guards (do not reorder above wall finiteness).
    if price > call_wall:
        return HostageState.ESCAPE_UP
    if price < put_wall:
        return HostageState.ESCAPE_DOWN

    near_call = _relative_distance(price, call_wall)
    near_put = _relative_distance(price, put_wall)
    if (near_call is not None and near_call <= threshold) or (near_put is not None and near_put <= threshold):
        return HostageState.PINNED

    if low < price < high:
        dist_call = abs(price - call_wall)
        dist_put = abs(price - put_wall)
        if dist_call < dist_put:
            return HostageState.PULL_TO_CALL_WALL
        if dist_put < dist_call:
            return HostageState.PULL_TO_PUT_WALL
        return HostageState.NEUTRAL

    return HostageState.NEUTRAL
