"""Screened candidate contract."""

from __future__ import annotations

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from dataclasses import dataclass

from qops.schemas.environment import DirectionalBias, IVState, RegimeLabel, SkewState, WallState
from qops.schemas.playbook import AllowedPlaybook, StructureBias


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

    allowed_playbook: AllowedPlaybook

    tradeability_pass: bool
    liquidity_pass: bool

    screener_reason: str
    skip_reason: str | None
