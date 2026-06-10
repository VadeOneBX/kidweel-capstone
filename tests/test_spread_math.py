"""Deterministic spread math checks for STRUCT-MATH-C1."""

from __future__ import annotations

import math

import pytest

from qops.risk.pmp_policy import min_rr_for_pmp
from qops.strategy.spread_math import SpreadMathInputs, evaluate_spread_math


def test_bull_call_debit_spread_economics() -> None:
    ev = evaluate_spread_math(
        SpreadMathInputs(
            structure_type="BULL_CALL_SPREAD",
            spread_width=5.0,
            net_debit_or_credit=1.50,
            reference_strike=100.0,
        )
    )
    assert ev.max_profit == pytest.approx(3.50)
    assert ev.max_loss == pytest.approx(1.50)
    assert ev.reward_risk == pytest.approx(2.3333333333)
    assert ev.break_even == pytest.approx(101.50)
    assert ev.capital_at_risk == pytest.approx(1.50)
    assert ev.passes_spread_math_gate is True


def test_bear_put_debit_spread_economics() -> None:
    ev = evaluate_spread_math(
        SpreadMathInputs(
            structure_type="BEAR_PUT_SPREAD",
            spread_width=5.0,
            net_debit_or_credit=1.75,
            reference_strike=200.0,
        )
    )
    assert ev.max_profit == pytest.approx(3.25)
    assert ev.max_loss == pytest.approx(1.75)
    assert ev.reward_risk == pytest.approx(1.8571428571)
    assert ev.break_even == pytest.approx(198.25)
    assert ev.passes_spread_math_gate is True


def test_bull_put_credit_spread_economics() -> None:
    ev = evaluate_spread_math(
        SpreadMathInputs(
            structure_type="BULL_PUT_CREDIT_SPREAD",
            spread_width=5.0,
            net_debit_or_credit=1.20,
            reference_strike=90.0,
        )
    )
    assert ev.max_profit == pytest.approx(1.20)
    assert ev.max_loss == pytest.approx(3.80)
    assert ev.reward_risk == pytest.approx(0.3157894737)
    assert ev.break_even == pytest.approx(88.80)
    assert ev.passes_spread_math_gate is True


def test_bear_call_credit_spread_economics() -> None:
    ev = evaluate_spread_math(
        SpreadMathInputs(
            structure_type="BEAR_CALL_CREDIT_SPREAD",
            spread_width=5.0,
            net_debit_or_credit=1.10,
            reference_strike=110.0,
        )
    )
    assert ev.max_profit == pytest.approx(1.10)
    assert ev.max_loss == pytest.approx(3.90)
    assert ev.reward_risk == pytest.approx(0.2820512821)
    assert ev.break_even == pytest.approx(111.10)
    assert ev.passes_spread_math_gate is True


def test_probability_gate_rr_required() -> None:
    p = 0.40
    assert min_rr_for_pmp(p) == pytest.approx(1.50)

    low_rr = evaluate_spread_math(
        SpreadMathInputs(
            structure_type="BULL_CALL_SPREAD",
            spread_width=5.0,
            net_debit_or_credit=2.10,
            reference_strike=100.0,
        ),
        probability_of_profit=p,
    )
    assert low_rr.reward_risk == pytest.approx(2.90 / 2.10)
    assert low_rr.rr_required == pytest.approx(1.50)
    assert low_rr.pass_reward_risk is False
    assert low_rr.passes_spread_math_gate is False

    high_rr = evaluate_spread_math(
        SpreadMathInputs(
            structure_type="BULL_CALL_SPREAD",
            spread_width=5.0,
            net_debit_or_credit=1.50,
            reference_strike=100.0,
        ),
        probability_of_profit=p,
    )
    assert high_rr.reward_risk == pytest.approx(2.3333333333)
    assert high_rr.pass_reward_risk is True
    assert high_rr.passes_spread_math_gate is True


@pytest.mark.parametrize("bad_p", [0.0, 1.0, -0.1, 1.1, math.nan, math.inf])
def test_invalid_probability_fails_closed(bad_p: float) -> None:
    ev = evaluate_spread_math(
        SpreadMathInputs(
            structure_type="BULL_CALL_SPREAD",
            spread_width=5.0,
            net_debit_or_credit=1.50,
            reference_strike=100.0,
        ),
        probability_of_profit=bad_p,
    )
    assert ev.pass_probability is False
    assert ev.pass_ev is False
    assert ev.passes_spread_math_gate is False
    assert "invalid_probability_of_profit" in ev.failure_reasons


def test_missing_probability_is_incomplete_not_pass_ev() -> None:
    ev = evaluate_spread_math(
        SpreadMathInputs(
            structure_type="BULL_CALL_SPREAD",
            spread_width=5.0,
            net_debit_or_credit=1.50,
            reference_strike=100.0,
        ),
    )
    assert ev.ev_status == "INCOMPLETE"
    assert ev.probability_status == "INCOMPLETE"
    assert ev.pass_ev is False
    assert ev.pass_probability is False
    assert ev.expected_value is None
    assert ev.passes_spread_math_gate is True


def test_floored_pmp_bucket_uses_conservative_min_rr() -> None:
    ev = evaluate_spread_math(
        SpreadMathInputs(
            structure_type="BULL_CALL_SPREAD",
            spread_width=5.0,
            net_debit_or_credit=1.75,
            reference_strike=100.0,
        ),
        probability_of_profit=0.47,
    )
    assert ev.rr_required == pytest.approx(1.22)
    assert ev.reward_risk == pytest.approx(3.25 / 1.75)
    assert ev.pass_reward_risk is True


def test_pmp_outside_table_fails_spread_math() -> None:
    ev = evaluate_spread_math(
        SpreadMathInputs(
            structure_type="BULL_CALL_SPREAD",
            spread_width=5.0,
            net_debit_or_credit=1.50,
            reference_strike=100.0,
        ),
        probability_of_profit=0.24,
    )
    assert ev.passes_spread_math_gate is False
    assert "pmp_outside_supported_table" in ev.failure_reasons
