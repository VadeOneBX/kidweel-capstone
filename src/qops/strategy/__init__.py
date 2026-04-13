"""Deterministic strategy scaffolding: expiry, structure, payoff, and RR math."""

from __future__ import annotations

from qops.strategy.constants import (
    DEFAULT_BEAR_PUT_WIDTH,
    DEFAULT_BULL_CALL_WIDTH,
    MAX_STRIKE_DISTANCE_PCT,
    MIN_DTE,
    MIN_STRIKE_INCREMENT,
)
from qops.strategy.expiry_selector import select_expiry
from qops.strategy.payoff import (
    debit_spread_breakeven,
    debit_spread_max_loss,
    debit_spread_max_profit,
)
from qops.strategy.rr import reward_risk_ratio, validate_rr_inputs
from qops.strategy.spread_builder import build_structure_candidate

__all__ = [
    "DEFAULT_BEAR_PUT_WIDTH",
    "DEFAULT_BULL_CALL_WIDTH",
    "MAX_STRIKE_DISTANCE_PCT",
    "MIN_DTE",
    "MIN_STRIKE_INCREMENT",
    "build_structure_candidate",
    "debit_spread_breakeven",
    "debit_spread_max_loss",
    "debit_spread_max_profit",
    "reward_risk_ratio",
    "select_expiry",
    "validate_rr_inputs",
]
