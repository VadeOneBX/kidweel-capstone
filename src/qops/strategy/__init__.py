"""Deterministic strategy scaffolding: expiry, structure, payoff, and RR math."""

from __future__ import annotations

from importlib import import_module

from qops.strategy.constants import (
    DEFAULT_BEAR_PUT_WIDTH,
    DEFAULT_BULL_CALL_WIDTH,
    MAX_STRIKE_DISTANCE_PCT,
    MIN_DTE,
    MIN_STRIKE_INCREMENT,
)
from qops.strategy.payoff import (
    debit_spread_breakeven,
    debit_spread_max_loss,
    debit_spread_max_profit,
)
from qops.strategy.rr import reward_risk_ratio, validate_rr_inputs

__all__ = [
    "DEFAULT_BEAR_PUT_WIDTH",
    "DEFAULT_BULL_CALL_WIDTH",
    "MAX_STRIKE_DISTANCE_PCT",
    "MIN_DTE",
    "MIN_STRIKE_INCREMENT",
    "SpreadMathEvaluation",
    "SpreadMathInputs",
    "build_structure_candidate",
    "evaluate_spread_math",
    "spread_math_allows_advance",
    "generate_spread_candidates",
    "debit_spread_breakeven",
    "debit_spread_max_loss",
    "debit_spread_max_profit",
    "reward_risk_ratio",
    "select_expiry",
    "validate_rr_inputs",
]

_LAZY_EXPORTS: dict[str, str] = {
    "SpreadMathEvaluation": "qops.strategy.spread_math",
    "SpreadMathInputs": "qops.strategy.spread_math",
    "build_structure_candidate": "qops.strategy.spread_builder",
    "evaluate_spread_math": "qops.strategy.spread_math",
    "select_expiry": "qops.strategy.expiry_selector",
    "spread_math_allows_advance": "qops.strategy.spread_math",
    "generate_spread_candidates": "qops.strategy.spread_candidate_generator",
}


def __getattr__(name: str) -> object:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value
