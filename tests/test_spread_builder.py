"""STRUCT-C1: canonical spread builder + spread math gate."""

from __future__ import annotations

import pytest

from qops.schemas.candidate import ScreenedCandidate
from qops.schemas.environment import (
    DirectionalBias,
    IVState,
    RegimeLabel,
    SkewState,
    WallState,
)
from qops.schemas.playbook import AllowedPlaybook, StructureBias
from qops.signals.classifier import (
    GammaRegimeState,
    PremiumPosture,
    SignalType,
    VolTriggerRelation,
)
from qops.strategy.spread_builder import build_structure_candidate


def _bias_for_playbook(playbook: AllowedPlaybook) -> StructureBias:
    return StructureBias(playbook.value)


def _screened_fixture(*, playbook: AllowedPlaybook) -> ScreenedCandidate:
    return ScreenedCandidate(
        symbol="SPY",
        underlying_price=425.0,
        dte_target=7,
        expiry_target="2026-06-20",
        regime_label=RegimeLabel.SQUEEZE_UP,
        structure_bias=_bias_for_playbook(playbook),
        confidence=72,
        gamma_ratio=0.41,
        iv_rank=0.35,
        iv_state=IVState.CHEAP_VOL,
        rr_rank=1.8,
        skew_state=SkewState.NEUTRAL,
        iv_1m=0.18,
        rv_1m=0.16,
        vrp=0.02,
        vrp_z=None,
        call_wall=430.0,
        put_wall=420.0,
        wall_state=WallState.BETWEEN_WALLS,
        directional_bias=DirectionalBias.BULLISH_BIAS,
        signal_type=SignalType.NONE,
        signal_horizon_days=(0, 999),
        wall_distance_pct=0.02,
        signal_strength="MEDIUM",
        vol_trigger=422.0,
        vol_trigger_relation=VolTriggerRelation.ABOVE_VOL_TRIGGER,
        gamma_regime_state=GammaRegimeState.POSITIVE_GAMMA,
        premium_posture=PremiumPosture.BUY_PREMIUM_FAVORED,
        dte_alignment_pass=True,
        allowed_playbook=playbook,
        tradeability_pass=True,
        liquidity_pass=True,
        screener_reason="struct_c1_fixture",
        skip_reason=None,
    )


def test_build_bull_call_passes_long_call_reference_strike() -> None:
    long_call_strike = 425.0
    structure = build_structure_candidate(
        _screened_fixture(playbook=AllowedPlaybook.BULL_CALL_SPREAD),
        1.50,
        reference_strike=long_call_strike,
    )
    assert structure.allowed_playbook == AllowedPlaybook.BULL_CALL_SPREAD
    assert structure.max_profit == pytest.approx(3.50)
    assert structure.debit_or_credit == pytest.approx(1.50)


def test_build_bear_put_passes_long_put_reference_strike() -> None:
    long_put_strike = 420.0
    structure = build_structure_candidate(
        _screened_fixture(playbook=AllowedPlaybook.BEAR_PUT_SPREAD),
        1.75,
        reference_strike=long_put_strike,
    )
    assert structure.allowed_playbook == AllowedPlaybook.BEAR_PUT_SPREAD
    assert structure.max_profit == pytest.approx(3.25)


def test_build_bull_put_credit_uses_credit_math() -> None:
    short_put_strike = 418.0
    structure = build_structure_candidate(
        _screened_fixture(playbook=AllowedPlaybook.BULL_PUT_CREDIT_SPREAD),
        1.20,
        reference_strike=short_put_strike,
    )
    assert structure.allowed_playbook == AllowedPlaybook.BULL_PUT_CREDIT_SPREAD
    assert structure.max_profit == pytest.approx(1.20)
    assert structure.max_loss == pytest.approx(3.80)
    assert structure.structure_type == "bullish_credit_spread"


def test_build_bear_call_credit_uses_credit_math() -> None:
    short_call_strike = 432.0
    structure = build_structure_candidate(
        _screened_fixture(playbook=AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD),
        1.10,
        reference_strike=short_call_strike,
    )
    assert structure.allowed_playbook == AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD
    assert structure.max_profit == pytest.approx(1.10)
    assert structure.max_loss == pytest.approx(3.90)
    assert structure.structure_type == "bearish_credit_spread"


def test_spread_math_failure_raises() -> None:
    with pytest.raises(ValueError, match="spread_math_gate_denied"):
        build_structure_candidate(
            _screened_fixture(playbook=AllowedPlaybook.BULL_CALL_SPREAD),
            1.50,
            reference_strike=425.0,
            probability_of_profit=0.24,
        )


@pytest.mark.parametrize(
    "playbook",
    [
        AllowedPlaybook.LONG_CALL_PARKED,
        AllowedPlaybook.LONG_GAMMA_HEDGE,
        AllowedPlaybook.SKIP,
    ],
)
def test_quarantined_or_skip_playbooks_not_buildable(playbook: AllowedPlaybook) -> None:
    candidate = _screened_fixture(playbook=playbook)
    if playbook != AllowedPlaybook.SKIP:
        object.__setattr__(candidate, "structure_bias", StructureBias(playbook.value))
    with pytest.raises(ValueError):
        build_structure_candidate(
            candidate,
            1.50,
            reference_strike=425.0,
        )
