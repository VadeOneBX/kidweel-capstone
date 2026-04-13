"""Trade structure candidate contract."""

from __future__ import annotations

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from dataclasses import dataclass

from qops.schemas.environment import DirectionalBias, IVState, RegimeLabel, SkewState, WallState
from qops.schemas.playbook import AllowedPlaybook


@dataclass(frozen=True, slots=True)
class TradeStructureCandidate:
    """Proposed structure with environment and playbook context."""

    symbol: str
    structure_type: str

    expiry: str
    width: float
    debit_or_credit: float

    max_profit: float
    max_loss: float
    rr_actual: float

    regime_label: RegimeLabel
    confidence: int
    gamma_ratio: float | None

    iv_state: IVState
    skew_state: SkewState
    wall_state: WallState
    directional_bias: DirectionalBias

    allowed_playbook: AllowedPlaybook

    structure_reason: str
