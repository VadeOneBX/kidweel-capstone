"""Validate and normalize screened-candidate handoff objects."""

from __future__ import annotations

import math

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from qops.schemas.candidate import ScreenedCandidate
from qops.schemas.playbook import AllowedPlaybook, StructureBias
from qops.signals.classifier import GammaRegimeState, PremiumPosture, SignalType, VolTriggerRelation
from qops.signals.horizon import signal_horizon_days

_EXECUTABLE_PLAYBOOKS: frozenset[AllowedPlaybook] = frozenset(
    {
        AllowedPlaybook.BULL_CALL_SPREAD,
        AllowedPlaybook.BEAR_PUT_SPREAD,
        AllowedPlaybook.BULL_PUT_CREDIT_SPREAD,
        AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD,
    }
)


def normalize_candidate(candidate: ScreenedCandidate) -> ScreenedCandidate:
    """
    Validate and return a canonical screened candidate.

    This function validates only; it does not re-derive canonical upstream fields.
    """
    if not isinstance(candidate, ScreenedCandidate):
        raise TypeError("candidate must be ScreenedCandidate")
    if not candidate.symbol or not candidate.symbol.strip():
        raise ValueError("candidate.symbol must be non-empty")
    if not math.isfinite(candidate.underlying_price) or candidate.underlying_price <= 0.0:
        raise ValueError("candidate.underlying_price must be > 0")
    if candidate.dte_target < 0:
        raise ValueError("candidate.dte_target must be >= 0")
    if not candidate.expiry_target or not candidate.expiry_target.strip():
        raise ValueError("candidate.expiry_target must be non-empty")
    if candidate.confidence is None:
        raise ValueError("candidate.confidence is required and canonical")
    if not (0 <= candidate.confidence <= 100):
        raise ValueError("candidate.confidence must be between 0 and 100")

    if candidate.regime_label is None:
        raise ValueError("candidate.regime_label is required and canonical")
    if candidate.structure_bias is None:
        raise ValueError("candidate.structure_bias is required and canonical")
    if candidate.allowed_playbook is None:
        raise ValueError("candidate.allowed_playbook is required")

    if candidate.allowed_playbook in _EXECUTABLE_PLAYBOOKS:
        if not candidate.tradeability_pass:
            raise ValueError("executable candidate requires tradeability_pass=True")
        if not candidate.liquidity_pass:
            raise ValueError("executable candidate requires liquidity_pass=True")

    if not isinstance(candidate.signal_type, SignalType):
        raise ValueError("candidate.signal_type must be SignalType")
    if (
        not isinstance(candidate.signal_horizon_days, tuple)
        or len(candidate.signal_horizon_days) != 2
        or not all(isinstance(v, int) for v in candidate.signal_horizon_days)
    ):
        raise ValueError("candidate.signal_horizon_days must be tuple[int, int]")
    min_days, max_days = candidate.signal_horizon_days
    if min_days < 0 or max_days < min_days:
        raise ValueError("candidate.signal_horizon_days must be coherent and non-negative")
    expected_horizon = signal_horizon_days(candidate.signal_type)
    if candidate.signal_horizon_days != expected_horizon:
        raise ValueError("candidate.signal_horizon_days must match canonical signal_type horizon")

    if candidate.wall_distance_pct is not None:
        if not math.isfinite(candidate.wall_distance_pct) or candidate.wall_distance_pct < 0.0:
            raise ValueError("candidate.wall_distance_pct must be None or finite >= 0")

    if candidate.signal_strength not in {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}:
        raise ValueError("candidate.signal_strength must be one of HIGH, MEDIUM, LOW, UNKNOWN")

    if candidate.vol_trigger is not None and (
        not math.isfinite(candidate.vol_trigger) or candidate.vol_trigger <= 0.0
    ):
        raise ValueError("candidate.vol_trigger must be None or finite > 0")
    if not isinstance(candidate.vol_trigger_relation, VolTriggerRelation):
        raise ValueError("candidate.vol_trigger_relation must be VolTriggerRelation")
    if not isinstance(candidate.gamma_regime_state, GammaRegimeState):
        raise ValueError("candidate.gamma_regime_state must be GammaRegimeState")
    if not isinstance(candidate.premium_posture, PremiumPosture):
        raise ValueError("candidate.premium_posture must be PremiumPosture")

    expected_alignment = min_days <= candidate.dte_target <= max_days
    if candidate.signal_type == SignalType.NONE:
        expected_alignment = True
    if candidate.dte_alignment_pass != expected_alignment:
        raise ValueError("candidate.dte_alignment_pass is inconsistent with signal_horizon_days")

    if (
        candidate.allowed_playbook == AllowedPlaybook.BULL_CALL_SPREAD
        and candidate.structure_bias != StructureBias.BULL_CALL_SPREAD
    ):
        raise ValueError(
            "allowed_playbook BULL_CALL_SPREAD must align with structure_bias BULL_CALL_SPREAD"
        )
    if (
        candidate.allowed_playbook == AllowedPlaybook.BEAR_PUT_SPREAD
        and candidate.structure_bias != StructureBias.BEAR_PUT_SPREAD
    ):
        raise ValueError(
            "allowed_playbook BEAR_PUT_SPREAD must align with structure_bias BEAR_PUT_SPREAD"
        )
    if (
        candidate.allowed_playbook == AllowedPlaybook.BULL_PUT_CREDIT_SPREAD
        and candidate.structure_bias != StructureBias.BULL_PUT_CREDIT_SPREAD
    ):
        raise ValueError(
            "allowed_playbook BULL_PUT_CREDIT_SPREAD must align with structure_bias "
            "BULL_PUT_CREDIT_SPREAD"
        )
    if (
        candidate.allowed_playbook == AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD
        and candidate.structure_bias != StructureBias.BEAR_CALL_CREDIT_SPREAD
    ):
        raise ValueError(
            "allowed_playbook BEAR_CALL_CREDIT_SPREAD must align with structure_bias "
            "BEAR_CALL_CREDIT_SPREAD"
        )

    return candidate
