"""Signal classifiers, horizons, and deterministic alignment helpers."""

from __future__ import annotations

from importlib import import_module

from qops.signals.classifier import (
    GammaRegimeState,
    PremiumPosture,
    SignalType,
    VolTriggerRelation,
    classify_gamma_regime_state,
    classify_premium_posture,
    classify_signal_strength,
    classify_signal_type,
    classify_vol_trigger_relation,
    compute_wall_distance_pct,
)
from qops.signals.constants import (
    SQUEEZE_HORIZON_MAX_DAYS,
    SQUEEZE_HORIZON_MIN_DAYS,
    VOL_TRIGGER_AT_BAND,
    WALL_REVERSAL_HORIZON_MAX_DAYS,
    WALL_REVERSAL_HORIZON_MIN_DAYS,
    WALL_REVERSAL_MAX_DISTANCE_PCT,
    WALL_REVERSAL_SOFT_DISTANCE_PCT,
)
from qops.signals.horizon import signal_horizon_days

__all__ = [
    "GammaRegimeState",
    "PremiumPosture",
    "SQUEEZE_HORIZON_MAX_DAYS",
    "SQUEEZE_HORIZON_MIN_DAYS",
    "SignalType",
    "VOL_TRIGGER_AT_BAND",
    "VolTriggerRelation",
    "WALL_REVERSAL_HORIZON_MAX_DAYS",
    "WALL_REVERSAL_HORIZON_MIN_DAYS",
    "WALL_REVERSAL_MAX_DISTANCE_PCT",
    "WALL_REVERSAL_SOFT_DISTANCE_PCT",
    "classify_gamma_regime_state",
    "classify_premium_posture",
    "classify_signal_strength",
    "classify_signal_type",
    "classify_vol_trigger_relation",
    "compute_wall_distance_pct",
    "dte_aligns_with_signal",
    "signal_alignment_passes",
    "signal_horizon_days",
]

_LAZY_EXPORTS: dict[str, str] = {
    "dte_aligns_with_signal": "qops.signals.alignment",
    "signal_alignment_passes": "qops.signals.alignment",
}


def __getattr__(name: str) -> object:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value
