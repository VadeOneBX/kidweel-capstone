"""Deterministic tradeability gates for screened candidates."""

from __future__ import annotations

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from qops.schemas.candidate import ScreenedCandidate
from qops.schemas.playbook import AllowedPlaybook
from qops.signals.classifier import PremiumPosture, SignalType
from qops.signals.constants import WALL_REVERSAL_MAX_DISTANCE_PCT
from qops.strategy.constants import MIN_DTE

_EXECUTABLE_PLAYBOOKS: frozenset[AllowedPlaybook] = frozenset(
    {
        AllowedPlaybook.BULL_CALL_SPREAD,
        AllowedPlaybook.BEAR_PUT_SPREAD,
    }
)


def has_minimum_dte(candidate: ScreenedCandidate, min_dte: int) -> bool:
    """Return True if candidate meets the minimum DTE requirement."""
    return candidate.dte_target >= min_dte


def is_tradeable(candidate: ScreenedCandidate) -> tuple[bool, str]:
    """
    Return (pass_flag, reason) for deterministic tradeability checks.

    LONG_CALL_PARKED and LONG_GAMMA_HEDGE are valid states but not tradeable in this packet.
    """
    if not candidate.tradeability_pass:
        return False, "tradeability_flag_false"
    if not candidate.liquidity_pass:
        return False, "liquidity_flag_false"
    if not has_minimum_dte(candidate, MIN_DTE):
        return False, f"dte_below_minimum_{MIN_DTE}"
    if not candidate.dte_alignment_pass:
        return False, "dte_alignment_pass_false"

    if candidate.allowed_playbook == AllowedPlaybook.SKIP:
        return False, "allowed_playbook_skip_non_executable"
    if candidate.allowed_playbook == AllowedPlaybook.LONG_CALL_PARKED:
        return False, "allowed_playbook_long_call_parked_non_executable"
    if candidate.allowed_playbook == AllowedPlaybook.LONG_GAMMA_HEDGE:
        return False, "allowed_playbook_long_gamma_hedge_non_executable"
    if candidate.allowed_playbook not in _EXECUTABLE_PLAYBOOKS:
        return False, "allowed_playbook_not_supported_in_packet"

    if candidate.signal_type == SignalType.WALL_REVERSAL:
        if candidate.wall_distance_pct is None:
            return False, "wall_reversal_wall_distance_missing"
        if candidate.wall_distance_pct > WALL_REVERSAL_MAX_DISTANCE_PCT:
            return False, "wall_reversal_wall_distance_too_far"
        if candidate.signal_strength == "LOW":
            return False, "wall_reversal_signal_strength_low"

    if (
        candidate.allowed_playbook in _EXECUTABLE_PLAYBOOKS
        and candidate.premium_posture == PremiumPosture.PREMIUM_AVOID
    ):
        return False, "premium_posture_avoid_for_premium_buying_playbook"

    return True, "tradeable"
