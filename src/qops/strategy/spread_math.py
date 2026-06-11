"""Option Alpha-style deterministic spread economics and validation gate."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from qops.risk.pmp_policy import min_rr_for_pmp, passes_pmp_rr_gate
from qops.schemas.playbook import AllowedPlaybook
from qops.schemas.structure import TradeStructureCandidate
from qops.strategy.payoff import (
    debit_spread_breakeven,
    debit_spread_max_loss,
    debit_spread_max_profit,
)
from qops.strategy.rr import reward_risk_ratio

EvStatus = Literal["PASS", "WATCH", "INCOMPLETE", "FAIL"]
ProbabilityStatus = Literal["PASS", "FAIL", "WATCH", "INCOMPLETE"]

DEBIT_STRUCTURE_TYPES = frozenset(
    {
        AllowedPlaybook.BULL_CALL_SPREAD.value,
        AllowedPlaybook.BEAR_PUT_SPREAD.value,
    }
)
CREDIT_STRUCTURE_TYPES = frozenset(
    {
        AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value,
        AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD.value,
    }
)
SUPPORTED_STRUCTURE_TYPES = DEBIT_STRUCTURE_TYPES | CREDIT_STRUCTURE_TYPES


@dataclass(frozen=True, slots=True)
class SpreadMathInputs:
    """Raw spread economics for math evaluation."""

    structure_type: str
    spread_width: float
    net_debit_or_credit: float
    reference_strike: float


@dataclass(frozen=True, slots=True)
class SpreadMathEvaluation:
    """Deterministic spread math outcome; advisory layers may not upgrade a failed result."""

    structure_type: str
    spread_width: float
    net_debit_or_credit: float
    max_profit: float
    max_loss: float
    reward_risk: float
    break_even: float | None
    capital_at_risk: float
    probability_of_profit: float | None
    expected_value: float | None
    rr_required: float | None
    pass_reward_risk: bool
    pass_probability: bool
    pass_ev: bool
    ev_status: EvStatus
    probability_status: ProbabilityStatus
    passes_spread_math_gate: bool
    failure_reasons: tuple[str, ...]


def _credit_spread_max_profit(net_credit: float) -> float:
    if net_credit <= 0:
        raise ValueError("net_credit must be > 0")
    return net_credit


def _credit_spread_max_loss(width: float, net_credit: float) -> float:
    if width <= 0:
        raise ValueError("width must be > 0")
    if net_credit <= 0:
        raise ValueError("net_credit must be > 0")
    max_loss = width - net_credit
    if max_loss <= 0:
        raise ValueError("credit spread max_loss must be > 0")
    return max_loss


def _credit_spread_breakeven(structure_type: str, short_strike: float, net_credit: float) -> float:
    if net_credit <= 0:
        raise ValueError("net_credit must be > 0")
    if structure_type == AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value:
        return short_strike - net_credit
    if structure_type == AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD.value:
        return short_strike + net_credit
    raise ValueError(f"unsupported credit structure_type for breakeven: {structure_type}")


def _compute_core_economics(
    inputs: SpreadMathInputs,
) -> tuple[float, float, float, float | None, list[str]]:
    """Return max_profit, max_loss, reward_risk, break_even, failure_reasons."""
    reasons: list[str] = []
    st = inputs.structure_type
    width = inputs.spread_width
    premium = inputs.net_debit_or_credit
    strike = inputs.reference_strike

    if st not in SUPPORTED_STRUCTURE_TYPES:
        reasons.append("unsupported_structure_type")
        return 0.0, 0.0, 0.0, None, reasons

    if not math.isfinite(width) or width <= 0.0:
        reasons.append("invalid_spread_width")
    if not math.isfinite(premium) or premium <= 0.0:
        reasons.append("invalid_net_debit_or_credit")
    if not math.isfinite(strike):
        reasons.append("invalid_reference_strike")

    max_profit = 0.0
    max_loss = 0.0
    reward_risk = 0.0
    break_even: float | None = None

    if st in DEBIT_STRUCTURE_TYPES:
        try:
            max_profit = debit_spread_max_profit(width=width, debit=premium)
            max_loss = debit_spread_max_loss(debit=premium)
            bullish = st == AllowedPlaybook.BULL_CALL_SPREAD.value
            break_even = debit_spread_breakeven(long_strike=strike, debit=premium, bullish=bullish)
            reward_risk = reward_risk_ratio(max_profit=max_profit, max_loss=max_loss)
        except ValueError:
            reasons.append("debit_spread_economics_invalid")
    elif st in CREDIT_STRUCTURE_TYPES:
        try:
            max_profit = _credit_spread_max_profit(net_credit=premium)
            max_loss = _credit_spread_max_loss(width=width, net_credit=premium)
            break_even = _credit_spread_breakeven(st, short_strike=strike, net_credit=premium)
            reward_risk = reward_risk_ratio(max_profit=max_profit, max_loss=max_loss)
        except ValueError:
            reasons.append("credit_spread_economics_invalid")

    for label, value in (
        ("max_profit", max_profit),
        ("max_loss", max_loss),
        ("reward_risk", reward_risk),
    ):
        if not math.isfinite(value) or value <= 0.0:
            reasons.append(f"invalid_{label}")

    if break_even is None:
        reasons.append("missing_break_even")
    elif not math.isfinite(break_even):
        reasons.append("invalid_break_even")

    return max_profit, max_loss, reward_risk, break_even, reasons


def evaluate_spread_math(
    candidate_or_inputs: SpreadMathInputs | TradeStructureCandidate,
    *,
    probability_of_profit: float | None = None,
    reference_strike: float | None = None,
) -> SpreadMathEvaluation:
    """
    Evaluate Option Alpha-style spread math for a debit or credit vertical spread.

    When passing TradeStructureCandidate, reference_strike is required (long strike for
    debit spreads, short strike for credit spreads).
    """
    if isinstance(candidate_or_inputs, TradeStructureCandidate):
        structure = candidate_or_inputs
        if reference_strike is None:
            raise ValueError("reference_strike is required for TradeStructureCandidate inputs")
        inputs = SpreadMathInputs(
            structure_type=structure.allowed_playbook.value,
            spread_width=structure.width,
            net_debit_or_credit=structure.debit_or_credit,
            reference_strike=reference_strike,
        )
    else:
        inputs = candidate_or_inputs

    max_profit, max_loss, reward_risk, break_even, core_reasons = _compute_core_economics(inputs)
    failure_reasons = list(core_reasons)
    capital_at_risk = max_loss

    rr_required: float | None = None
    pass_reward_risk = False
    pass_probability = False
    probability_status: ProbabilityStatus = "INCOMPLETE"
    expected_value: float | None = None
    pass_ev = False
    ev_status: EvStatus = "INCOMPLETE"

    core_valid = not core_reasons

    if probability_of_profit is None:
        probability_status = "INCOMPLETE"
        ev_status = "INCOMPLETE"
        pass_probability = False
        pass_ev = False
        if core_valid:
            pass_reward_risk = False
    else:
        p = probability_of_profit
        if not math.isfinite(p) or p <= 0.0 or p >= 1.0:
            failure_reasons.append("invalid_probability_of_profit")
            probability_status = "FAIL"
            ev_status = "FAIL"
            pass_probability = False
            pass_ev = False
            pass_reward_risk = False
        else:
            try:
                rr_required = min_rr_for_pmp(p)
                expected_value = p * max_profit - (1.0 - p) * max_loss
                if not math.isfinite(expected_value):
                    failure_reasons.append("invalid_expected_value")
                    ev_status = "FAIL"
                elif expected_value > 0.0:
                    pass_ev = True
                    ev_status = "PASS"
                else:
                    pass_ev = False
                    ev_status = "WATCH"
                    failure_reasons.append("non_positive_expected_value")

                pass_probability = True
                probability_status = "PASS"
                pass_reward_risk = core_valid and passes_pmp_rr_gate(p, reward_risk)
                if core_valid and not pass_reward_risk:
                    failure_reasons.append("insufficient_reward_risk_for_probability")
            except ValueError as exc:
                reason = str(exc)
                if "supported table range" in reason or "supported table bucket" in reason:
                    failure_reasons.append("pmp_outside_supported_table")
                else:
                    failure_reasons.append("invalid_probability_of_profit")
                probability_status = "FAIL"
                ev_status = "FAIL"
                pass_probability = False
                pass_ev = False
                pass_reward_risk = False

    if not core_valid:
        pass_reward_risk = False
        pass_ev = False
        if ev_status == "INCOMPLETE":
            ev_status = "FAIL"

    passes_gate = core_valid and not any(
        r in failure_reasons
        for r in ("invalid_probability_of_profit", "pmp_outside_supported_table")
    )
    if probability_of_profit is not None and core_valid and probability_status == "PASS":
        passes_gate = passes_gate and pass_reward_risk

    return SpreadMathEvaluation(
        structure_type=inputs.structure_type,
        spread_width=inputs.spread_width,
        net_debit_or_credit=inputs.net_debit_or_credit,
        max_profit=max_profit,
        max_loss=max_loss,
        reward_risk=reward_risk,
        break_even=break_even,
        capital_at_risk=capital_at_risk,
        probability_of_profit=probability_of_profit,
        expected_value=expected_value,
        rr_required=rr_required,
        pass_reward_risk=pass_reward_risk,
        pass_probability=pass_probability,
        pass_ev=pass_ev,
        ev_status=ev_status,
        probability_status=probability_status,
        passes_spread_math_gate=passes_gate,
        failure_reasons=tuple(dict.fromkeys(failure_reasons)),
    )


def spread_math_allows_advance(evaluation: SpreadMathEvaluation) -> tuple[bool, str]:
    """Return (allowed, reason) for structure advancement before risk / ML / transport."""
    if evaluation.passes_spread_math_gate:
        return True, "spread_math_pass"
    if evaluation.failure_reasons:
        return False, evaluation.failure_reasons[0]
    return False, "spread_math_failed"
