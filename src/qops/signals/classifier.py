"""Deterministic signal classification and posture helpers."""

from __future__ import annotations

from enum import Enum

from qops.signals.constants import (
    WALL_REVERSAL_MAX_DISTANCE_PCT,
    WALL_REVERSAL_SOFT_DISTANCE_PCT,
)


class SignalType(str, Enum):
    """Bounded dominant signal classification for candidate alignment."""

    SQUEEZE = "SQUEEZE"
    WALL_REVERSAL = "WALL_REVERSAL"
    NONE = "NONE"


class VolTriggerRelation(str, Enum):
    """Price relation to SpotGamma vol trigger level."""

    ABOVE_VOL_TRIGGER = "ABOVE_VOL_TRIGGER"
    BELOW_VOL_TRIGGER = "BELOW_VOL_TRIGGER"
    AT_VOL_TRIGGER = "AT_VOL_TRIGGER"
    UNKNOWN = "UNKNOWN"


class GammaRegimeState(str, Enum):
    """Mapped gamma regime from vol trigger relation."""

    POSITIVE_GAMMA = "POSITIVE_GAMMA"
    NEGATIVE_GAMMA = "NEGATIVE_GAMMA"
    TRANSITION = "TRANSITION"
    UNKNOWN = "UNKNOWN"


class PremiumPosture(str, Enum):
    """Premium posture for deterministic gating and diagnostics."""

    BUY_PREMIUM_FAVORED = "BUY_PREMIUM_FAVORED"
    SELL_PREMIUM_FAVORED = "SELL_PREMIUM_FAVORED"
    PREMIUM_AVOID = "PREMIUM_AVOID"
    UNKNOWN = "UNKNOWN"


def compute_wall_distance_pct(price: float, wall: float | None) -> float | None:
    """
    Return abs(price - wall) / price when wall is present.

    Returns None when wall is missing.
    """
    if price <= 0:
        raise ValueError("price must be > 0")
    if wall is None:
        return None
    return abs(price - wall) / price


def classify_signal_type(
    regime_label: str,
    wall_state: str,
) -> SignalType:
    """Classify the candidate into a bounded signal type."""
    if regime_label == "SQUEEZE_UP":
        return SignalType.SQUEEZE
    if wall_state in {"NEAR_CALL_WALL", "NEAR_PUT_WALL"}:
        return SignalType.WALL_REVERSAL
    return SignalType.NONE


def classify_signal_strength(
    signal_type: SignalType,
    wall_distance_pct: float | None,
) -> str:
    """Return HIGH, MEDIUM, LOW, or UNKNOWN."""
    if signal_type == SignalType.WALL_REVERSAL:
        if wall_distance_pct is None:
            return "UNKNOWN"
        if wall_distance_pct <= WALL_REVERSAL_MAX_DISTANCE_PCT:
            return "HIGH"
        if wall_distance_pct <= WALL_REVERSAL_SOFT_DISTANCE_PCT:
            return "MEDIUM"
        return "LOW"
    if signal_type == SignalType.SQUEEZE:
        return "HIGH"
    return "LOW"


def classify_vol_trigger_relation(
    price: float,
    vol_trigger: float | None,
    at_band: float,
) -> VolTriggerRelation:
    """Return ABOVE, BELOW, AT, or UNKNOWN vol trigger relation."""
    if price <= 0:
        raise ValueError("price must be > 0")
    if at_band < 0:
        raise ValueError("at_band must be >= 0")
    if vol_trigger is None:
        return VolTriggerRelation.UNKNOWN
    if abs(price - vol_trigger) / price <= at_band:
        return VolTriggerRelation.AT_VOL_TRIGGER
    if price > vol_trigger:
        return VolTriggerRelation.ABOVE_VOL_TRIGGER
    return VolTriggerRelation.BELOW_VOL_TRIGGER


def classify_gamma_regime_state(
    relation: VolTriggerRelation,
) -> GammaRegimeState:
    """Map vol trigger relation to gamma regime state."""
    if relation == VolTriggerRelation.ABOVE_VOL_TRIGGER:
        return GammaRegimeState.POSITIVE_GAMMA
    if relation == VolTriggerRelation.BELOW_VOL_TRIGGER:
        return GammaRegimeState.NEGATIVE_GAMMA
    if relation == VolTriggerRelation.AT_VOL_TRIGGER:
        return GammaRegimeState.TRANSITION
    return GammaRegimeState.UNKNOWN


def classify_premium_posture(
    regime_label: str,
    signal_type: SignalType,
    gamma_regime_state: GammaRegimeState,
    vrp_z: float | None,
) -> PremiumPosture:
    """Return BUY/SELL/AVOID/UNKNOWN premium posture deterministically."""
    if gamma_regime_state == GammaRegimeState.NEGATIVE_GAMMA and signal_type == SignalType.SQUEEZE:
        return PremiumPosture.PREMIUM_AVOID
    if gamma_regime_state == GammaRegimeState.NEGATIVE_GAMMA and regime_label == "BUY_PREMIUM":
        return PremiumPosture.PREMIUM_AVOID
    if regime_label in {"BUY_PREMIUM", "SQUEEZE_UP"} and gamma_regime_state in {
        GammaRegimeState.POSITIVE_GAMMA,
        GammaRegimeState.TRANSITION,
    }:
        return PremiumPosture.BUY_PREMIUM_FAVORED
    if vrp_z is not None and vrp_z >= 1.5:
        return PremiumPosture.SELL_PREMIUM_FAVORED
    return PremiumPosture.UNKNOWN
