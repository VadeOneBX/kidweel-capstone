"""Screened candidate contract."""

from __future__ import annotations

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from dataclasses import dataclass

from qops.schemas.environment import DirectionalBias, IVState, RegimeLabel, SkewState, WallState
from qops.schemas.playbook import AllowedPlaybook, StructureBias
from qops.signals.classifier import GammaRegimeState, PremiumPosture, SignalType, VolTriggerRelation


@dataclass(frozen=True, slots=True)
class ScreenedCandidate:
    """Normalized output from screening; carries canonical regime and structure intent."""

    symbol: str
    underlying_price: float

    dte_target: int
    expiry_target: str

    regime_label: RegimeLabel
    structure_bias: StructureBias
    confidence: int
    gamma_ratio: float | None

    iv_rank: float
    iv_state: IVState

    rr_rank: float
    skew_state: SkewState

    iv_1m: float
    rv_1m: float
    vrp: float
    vrp_z: float | None

    call_wall: float | None
    put_wall: float | None

    wall_state: WallState
    directional_bias: DirectionalBias

    signal_type: SignalType
    signal_horizon_days: tuple[int, int]
    wall_distance_pct: float | None
    signal_strength: str
    vol_trigger: float | None
    vol_trigger_relation: VolTriggerRelation
    gamma_regime_state: GammaRegimeState
    premium_posture: PremiumPosture
    dte_alignment_pass: bool

    allowed_playbook: AllowedPlaybook

    tradeability_pass: bool
    liquidity_pass: bool

    screener_reason: str
    skip_reason: str | None
