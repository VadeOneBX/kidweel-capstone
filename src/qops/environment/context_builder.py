"""Build EnvironmentSnapshot from a screened candidate without re-deriving canonical fields."""

from __future__ import annotations

import math

from qops.environment.constants import WALL_PROXIMITY_THRESHOLD
from qops.environment.hostage_classifier import classify_hostage_state
from qops.environment.iv_classifier import classify_iv_state
from qops.environment.wall_classifier import classify_wall_state

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from qops.schemas.candidate import ScreenedCandidate
from qops.schemas.environment import EnvironmentSnapshot, HostageState


def build_environment_snapshot(candidate: ScreenedCandidate) -> EnvironmentSnapshot:
    """
    Build a deterministic environment snapshot from a normalized screened candidate.

    Does not re-derive regime_label, confidence, or gamma_ratio. Uses candidate iv_state
    and wall_state as authoritative; compares to classifier outputs for consistency notes only.
    """
    reason_parts: list[str] = []

    if not candidate.symbol or not candidate.symbol.strip():
        reason_parts.append("invalid_symbol")

    if not math.isfinite(candidate.underlying_price) or candidate.underlying_price <= 0.0:
        reason_parts.append("invalid_underlying_price")

    derived_iv = classify_iv_state(candidate.iv_rank)
    if derived_iv != candidate.iv_state:
        reason_parts.append("iv_state_mismatch_with_iv_rank")

    derived_wall = classify_wall_state(
        candidate.underlying_price,
        candidate.call_wall,
        candidate.put_wall,
        WALL_PROXIMITY_THRESHOLD,
    )
    if derived_wall != candidate.wall_state:
        reason_parts.append("wall_state_mismatch_with_price_and_walls")

    hostage = classify_hostage_state(
        candidate.underlying_price,
        candidate.call_wall,
        candidate.put_wall,
        WALL_PROXIMITY_THRESHOLD,
    )
    if hostage == HostageState.UNKNOWN:
        reason_parts.append("hostage_unknown_or_incomplete_wall_data")

    env_label = "|".join(
        (
            f"REG:{candidate.regime_label.value}",
            f"IV:{candidate.iv_state.value}",
            f"SK:{candidate.skew_state.value}",
            f"W:{candidate.wall_state.value}",
            f"DIR:{candidate.directional_bias.value}",
            f"H:{hostage.value}",
        )
    )

    environment_reason = ";".join(reason_parts) if reason_parts else "aligned_with_candidate_fields"

    return EnvironmentSnapshot(
        symbol=candidate.symbol,
        regime_label=candidate.regime_label,
        confidence=candidate.confidence,
        gamma_ratio=candidate.gamma_ratio,
        iv_state=candidate.iv_state,
        skew_state=candidate.skew_state,
        wall_state=candidate.wall_state,
        directional_bias=candidate.directional_bias,
        hostage_state=hostage,
        environment_label=env_label,
        environment_reason=environment_reason,
    )
