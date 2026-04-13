"""Deterministic TradeStructureCandidate builder for executable debit spreads only."""

from __future__ import annotations

from qops.strategy.constants import DEFAULT_BEAR_PUT_WIDTH, DEFAULT_BULL_CALL_WIDTH
from qops.strategy.expiry_selector import select_expiry
from qops.strategy.payoff import debit_spread_max_loss, debit_spread_max_profit
from qops.strategy.rr import reward_risk_ratio

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from qops.schemas.candidate import ScreenedCandidate
from qops.schemas.playbook import AllowedPlaybook
from qops.schemas.structure import TradeStructureCandidate


def _width_for_playbook(playbook: AllowedPlaybook) -> float:
    if playbook == AllowedPlaybook.BULL_CALL_SPREAD:
        return DEFAULT_BULL_CALL_WIDTH
    if playbook == AllowedPlaybook.BEAR_PUT_SPREAD:
        return DEFAULT_BEAR_PUT_WIDTH
    raise ValueError(f"non-executable playbook for structure builder: {playbook.value}")


def _structure_type_for_playbook(playbook: AllowedPlaybook) -> str:
    if playbook == AllowedPlaybook.BULL_CALL_SPREAD:
        return "bullish_debit_spread"
    if playbook == AllowedPlaybook.BEAR_PUT_SPREAD:
        return "bearish_debit_spread"
    raise ValueError(f"unsupported playbook for structure type mapping: {playbook.value}")


def build_structure_candidate(
    candidate: ScreenedCandidate,
    debit_or_credit: float,
) -> TradeStructureCandidate:
    """
    Build a deterministic trade structure candidate from an executable screened candidate.

    Supports only BULL_CALL_SPREAD and BEAR_PUT_SPREAD in this packet.
    """
    if debit_or_credit <= 0:
        raise ValueError("debit_or_credit must be > 0 for debit spread scaffold")

    playbook = candidate.allowed_playbook
    if playbook not in {AllowedPlaybook.BULL_CALL_SPREAD, AllowedPlaybook.BEAR_PUT_SPREAD}:
        raise ValueError(f"non-executable allowed_playbook for C6: {playbook.value}")

    expiry = select_expiry(candidate)
    width = _width_for_playbook(playbook)
    if width <= 0:
        raise ValueError("width must be > 0")

    max_profit = debit_spread_max_profit(width=width, debit=debit_or_credit)
    max_loss = debit_spread_max_loss(debit=debit_or_credit)
    rr_actual = reward_risk_ratio(max_profit=max_profit, max_loss=max_loss)

    return TradeStructureCandidate(
        symbol=candidate.symbol,
        structure_type=_structure_type_for_playbook(playbook),
        expiry=expiry,
        width=width,
        debit_or_credit=debit_or_credit,
        max_profit=max_profit,
        max_loss=max_loss,
        rr_actual=rr_actual,
        regime_label=candidate.regime_label,
        confidence=candidate.confidence,
        gamma_ratio=candidate.gamma_ratio,
        iv_state=candidate.iv_state,
        skew_state=candidate.skew_state,
        wall_state=candidate.wall_state,
        directional_bias=candidate.directional_bias,
        allowed_playbook=playbook,
        structure_reason="deterministic_placeholder_width_scaffold_no_chain_selection",
    )
