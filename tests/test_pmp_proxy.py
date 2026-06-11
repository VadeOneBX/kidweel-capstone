"""PMP-C1: deterministic short-leg delta PMP proxy."""

from __future__ import annotations

from qops.risk.pmp_policy import min_rr_for_pmp
from qops.risk.pmp_proxy import SpreadPmpProxyInput, estimate_pmp_proxy
from qops.schemas.playbook import AllowedPlaybook


def test_bull_call_short_call_delta_proxy() -> None:
    result = estimate_pmp_proxy(
        SpreadPmpProxyInput(
            structure_type=AllowedPlaybook.BULL_CALL_SPREAD.value,
            short_leg_delta=0.35,
            short_leg_greeks_source="alpaca_snapshot",
        )
    )
    assert result.pmp == 0.35
    assert result.pmp_source == "short_leg_delta_proxy"
    assert result.pmp_status == "PMP_PROXY_AVAILABLE"
    assert min_rr_for_pmp(0.35) == 1.86
    assert result.confidence == "MEDIUM"


def test_bear_put_short_put_delta_proxy() -> None:
    result = estimate_pmp_proxy(
        SpreadPmpProxyInput(
            structure_type=AllowedPlaybook.BEAR_PUT_SPREAD.value,
            short_leg_delta=-0.40,
            short_leg_greeks_source="alpaca_snapshot",
        )
    )
    assert result.pmp == 0.40
    assert min_rr_for_pmp(0.40) == 1.50
    assert result.confidence == "MEDIUM"


def test_bull_put_credit_proxy() -> None:
    result = estimate_pmp_proxy(
        SpreadPmpProxyInput(
            structure_type=AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value,
            short_leg_delta=-0.30,
            short_leg_greeks_source="alpaca_snapshot",
        )
    )
    assert result.pmp == 0.70
    assert min_rr_for_pmp(0.70) == 0.43


def test_bear_call_credit_proxy() -> None:
    result = estimate_pmp_proxy(
        SpreadPmpProxyInput(
            structure_type=AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD.value,
            short_leg_delta=0.25,
            short_leg_greeks_source="alpaca_snapshot",
        )
    )
    assert result.pmp == 0.75
    assert min_rr_for_pmp(0.75) == 0.33


def test_missing_delta() -> None:
    result = estimate_pmp_proxy(
        SpreadPmpProxyInput(
            structure_type=AllowedPlaybook.BULL_CALL_SPREAD.value,
            short_leg_delta=None,
            short_leg_greeks_source="missing",
        )
    )
    assert result.pmp_status == "MISSING_INPUTS"
    assert result.pmp is None


def test_out_of_range_pmp() -> None:
    result = estimate_pmp_proxy(
        SpreadPmpProxyInput(
            structure_type=AllowedPlaybook.BULL_CALL_SPREAD.value,
            short_leg_delta=0.05,
            short_leg_greeks_source="alpaca_snapshot",
        )
    )
    assert result.pmp_status == "OUTSIDE_POLICY_RANGE"
    assert result.pmp is None


def test_computed_bs_low_confidence() -> None:
    result = estimate_pmp_proxy(
        SpreadPmpProxyInput(
            structure_type=AllowedPlaybook.BULL_CALL_SPREAD.value,
            short_leg_delta=0.35,
            short_leg_greeks_source="computed_bs",
        )
    )
    assert result.pmp_source == "short_leg_delta_proxy"
    assert result.confidence == "LOW"


def test_vendor_greeks_medium_confidence() -> None:
    result = estimate_pmp_proxy(
        SpreadPmpProxyInput(
            structure_type=AllowedPlaybook.BULL_CALL_SPREAD.value,
            short_leg_delta=0.35,
            short_leg_greeks_source="alpaca_snapshot",
        )
    )
    assert result.confidence == "MEDIUM"
