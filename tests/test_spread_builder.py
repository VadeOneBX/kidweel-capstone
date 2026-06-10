"""STRUCT-MATH-C2: build_structure_candidate callers pass reference_strike."""

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


def _screened_fixture(*, playbook: AllowedPlaybook) -> ScreenedCandidate:
    bias = (
        StructureBias.BULL_CALL_SPREAD
        if playbook == AllowedPlaybook.BULL_CALL_SPREAD
        else StructureBias.BEAR_PUT_SPREAD
    )
    return ScreenedCandidate(
        symbol="SPY",
        underlying_price=425.0,
        dte_target=7,
        expiry_target="2026-06-20",
        regime_label=RegimeLabel.SQUEEZE_UP,
        structure_bias=bias,
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
        screener_reason="c2_fixture",
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
