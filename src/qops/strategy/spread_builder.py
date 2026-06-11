"""Deterministic TradeStructureCandidate builder for canonical risk-defined spreads."""

from __future__ import annotations

from qops.strategy.constants import (
    DEFAULT_BEAR_CALL_CREDIT_WIDTH,
    DEFAULT_BEAR_PUT_WIDTH,
    DEFAULT_BULL_CALL_WIDTH,
    DEFAULT_BULL_PUT_CREDIT_WIDTH,
)
from qops.strategy.expiry_selector import select_expiry
from qops.strategy.payoff import (
    credit_spread_max_loss,
    credit_spread_max_profit,
    debit_spread_max_loss,
    debit_spread_max_profit,
)
from qops.strategy.rr import reward_risk_ratio
from qops.strategy.spread_math import evaluate_spread_math, spread_math_allows_advance

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from qops.schemas.candidate import ScreenedCandidate
from qops.schemas.playbook import AllowedPlaybook
from qops.schemas.structure import TradeStructureCandidate

CANONICAL_BUILDABLE_PLAYBOOKS: frozenset[AllowedPlaybook] = frozenset(
    {
        AllowedPlaybook.BULL_CALL_SPREAD,
        AllowedPlaybook.BEAR_PUT_SPREAD,
        AllowedPlaybook.BULL_PUT_CREDIT_SPREAD,
        AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD,
    }
)

DEBIT_PLAYBOOKS: frozenset[AllowedPlaybook] = frozenset(
    {
        AllowedPlaybook.BULL_CALL_SPREAD,
        AllowedPlaybook.BEAR_PUT_SPREAD,
    }
)

CREDIT_PLAYBOOKS: frozenset[AllowedPlaybook] = frozenset(
    {
        AllowedPlaybook.BULL_PUT_CREDIT_SPREAD,
        AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD,
    }
)

QUARANTINED_PLAYBOOKS: frozenset[AllowedPlaybook] = frozenset(
    {
        AllowedPlaybook.LONG_CALL_PARKED,
        AllowedPlaybook.LONG_GAMMA_HEDGE,
    }
)


def _width_for_playbook(playbook: AllowedPlaybook) -> float:
    if playbook == AllowedPlaybook.BULL_CALL_SPREAD:
        return DEFAULT_BULL_CALL_WIDTH
    if playbook == AllowedPlaybook.BEAR_PUT_SPREAD:
        return DEFAULT_BEAR_PUT_WIDTH
    if playbook == AllowedPlaybook.BULL_PUT_CREDIT_SPREAD:
        return DEFAULT_BULL_PUT_CREDIT_WIDTH
    if playbook == AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD:
        return DEFAULT_BEAR_CALL_CREDIT_WIDTH
    raise ValueError(f"non-buildable playbook for structure builder: {playbook.value}")


def _structure_type_for_playbook(playbook: AllowedPlaybook) -> str:
    if playbook == AllowedPlaybook.BULL_CALL_SPREAD:
        return "bullish_debit_spread"
    if playbook == AllowedPlaybook.BEAR_PUT_SPREAD:
        return "bearish_debit_spread"
    if playbook == AllowedPlaybook.BULL_PUT_CREDIT_SPREAD:
        return "bullish_credit_spread"
    if playbook == AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD:
        return "bearish_credit_spread"
    raise ValueError(f"unsupported playbook for structure type mapping: {playbook.value}")


def _economics_for_playbook(
    playbook: AllowedPlaybook,
    width: float,
    net_debit_or_credit: float,
) -> tuple[float, float, float]:
    if playbook in DEBIT_PLAYBOOKS:
        max_profit = debit_spread_max_profit(width=width, debit=net_debit_or_credit)
        max_loss = debit_spread_max_loss(debit=net_debit_or_credit)
    elif playbook in CREDIT_PLAYBOOKS:
        max_profit = credit_spread_max_profit(net_credit=net_debit_or_credit)
        max_loss = credit_spread_max_loss(width=width, net_credit=net_debit_or_credit)
    else:
        raise ValueError(f"unsupported playbook for economics: {playbook.value}")
    rr_actual = reward_risk_ratio(max_profit=max_profit, max_loss=max_loss)
    return max_profit, max_loss, rr_actual


def build_structure_candidate(
    candidate: ScreenedCandidate,
    debit_or_credit: float,
    *,
    reference_strike: float,
    probability_of_profit: float | None = None,
) -> TradeStructureCandidate:
    """
    Build a deterministic trade structure candidate for a canonical multi-leg spread.

    Requires reference_strike (long strike for debit spreads, short strike for credit spreads).
    Every build runs evaluate_spread_math; failures fail closed.
    """
    if debit_or_credit <= 0:
        raise ValueError("debit_or_credit must be > 0")

    playbook = candidate.allowed_playbook
    if playbook == AllowedPlaybook.SKIP:
        raise ValueError("SKIP is not buildable via spread_builder")
    if playbook in QUARANTINED_PLAYBOOKS:
        raise ValueError(f"quarantined non-canonical playbook: {playbook.value}")
    if playbook not in CANONICAL_BUILDABLE_PLAYBOOKS:
        raise ValueError(f"non-canonical allowed_playbook for structure build: {playbook.value}")

    expiry = select_expiry(candidate)
    width = _width_for_playbook(playbook)
    if width <= 0:
        raise ValueError("width must be > 0")

    max_profit, max_loss, rr_actual = _economics_for_playbook(playbook, width, debit_or_credit)

    structure = TradeStructureCandidate(
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

    math_eval = evaluate_spread_math(
        structure,
        reference_strike=reference_strike,
        probability_of_profit=probability_of_profit,
    )
    allowed, reason = spread_math_allows_advance(math_eval)
    if not allowed:
        detail = ",".join(math_eval.failure_reasons) or reason
        raise ValueError(f"spread_math_gate_denied:{detail}")

    return structure
