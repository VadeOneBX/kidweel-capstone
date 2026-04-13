"""Detect conflicts between upstream structure intent and environment."""

from __future__ import annotations

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from qops.schemas.environment import (
    DirectionalBias,
    EnvironmentSnapshot,
    HostageState,
    RegimeLabel,
    WallState,
)
from qops.schemas.playbook import StructureBias


def has_playbook_conflict(
    structure_bias: StructureBias,
    environment: EnvironmentSnapshot,
) -> tuple[bool, str]:
    """
    Return (conflict_flag, reason) for mismatches between upstream structure intent
    and current environment state.
    """
    if structure_bias == StructureBias.SKIP:
        return False, "upstream_skip_no_conflict"

    if environment.wall_state == WallState.UNKNOWN:
        return True, "wall_state_unknown"

    if environment.hostage_state == HostageState.UNKNOWN:
        return True, "hostage_state_unknown"

    if structure_bias == StructureBias.BULL_CALL_SPREAD:
        if environment.directional_bias == DirectionalBias.BEARISH_BIAS:
            return True, "bullish_structure_with_bearish_directional_bias"
        if environment.regime_label == RegimeLabel.SELL_PREMIUM:
            return True, "bullish_structure_under_sell_premium_regime"

    if structure_bias == StructureBias.BEAR_PUT_SPREAD:
        if environment.directional_bias == DirectionalBias.BULLISH_BIAS:
            return True, "bearish_structure_with_bullish_directional_bias"
        if environment.regime_label in {RegimeLabel.BUY_PREMIUM, RegimeLabel.SQUEEZE_UP}:
            return True, "bearish_structure_under_bullish_regime"

    if environment.regime_label == RegimeLabel.NEUTRAL and environment.directional_bias == DirectionalBias.NEUTRAL_BIAS:
        if structure_bias in {StructureBias.BULL_CALL_SPREAD, StructureBias.BEAR_PUT_SPREAD}:
            return True, "neutral_regime_with_weak_directional_support"

    if structure_bias == StructureBias.LONG_CALL_PARKED:
        if environment.directional_bias == DirectionalBias.BEARISH_BIAS:
            return True, "parked_long_call_in_bearish_environment"
        if environment.hostage_state in {HostageState.ESCAPE_DOWN, HostageState.PULL_TO_PUT_WALL}:
            return True, "non_executable_parked_bias_with_downside_hostage_pressure"

    if structure_bias == StructureBias.LONG_GAMMA_HEDGE:
        if environment.directional_bias == DirectionalBias.BULLISH_BIAS:
            return True, "gamma_hedge_in_bullish_environment"
        if environment.hostage_state in {HostageState.ESCAPE_UP, HostageState.PULL_TO_CALL_WALL}:
            return True, "non_executable_hedge_bias_with_upside_hostage_pressure"

    if "mismatch" in environment.environment_reason:
        return True, "environment_reports_field_mismatch"

    return False, "no_conflict_detected"
