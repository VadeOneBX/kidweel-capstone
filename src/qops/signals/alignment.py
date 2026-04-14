"""Deterministic helpers for signal and DTE alignment checks."""

from __future__ import annotations

from qops.schemas.candidate import ScreenedCandidate
from qops.signals.classifier import PremiumPosture, SignalType
from qops.signals.constants import WALL_REVERSAL_MAX_DISTANCE_PCT
from qops.signals.horizon import signal_horizon_days


def dte_aligns_with_signal(
    signal_type: SignalType,
    dte_target: int,
) -> bool:
    """Return True if candidate DTE matches the signal horizon."""
    if signal_type == SignalType.NONE:
        return True
    min_days, max_days = signal_horizon_days(signal_type)
    return min_days <= dte_target <= max_days


def signal_alignment_passes(candidate: ScreenedCandidate) -> tuple[bool, str]:
    """
    Return (pass_flag, reason) for whether signal, wall distance, vol trigger,
    premium posture, and DTE align.
    """
    if candidate.signal_type == SignalType.SQUEEZE:
        if not dte_aligns_with_signal(candidate.signal_type, candidate.dte_target):
            return False, "dte_misaligned_for_squeeze"
        if candidate.premium_posture == PremiumPosture.PREMIUM_AVOID:
            return False, "premium_posture_avoid"
        return True, "squeeze_horizon_aligned"

    if candidate.signal_type == SignalType.WALL_REVERSAL:
        if candidate.wall_distance_pct is None:
            return False, "wall_distance_missing"
        if candidate.wall_distance_pct > WALL_REVERSAL_MAX_DISTANCE_PCT:
            return False, "wall_distance_too_far"
        if not dte_aligns_with_signal(candidate.signal_type, candidate.dte_target):
            return False, "dte_misaligned_for_wall_reversal"
        return True, "wall_reversal_aligned"

    return True, "signal_type_none"
