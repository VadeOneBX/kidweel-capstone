"""Risk and approval evaluation contract."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TradeEvaluation:
    """Typed risk and approval outcome for a evaluated trade."""

    symbol: str
    playbook: str

    pmp: float
    rr_required: float
    rr_actual: float

    max_profit: float
    max_loss: float

    tp_rule: str
    sl_rule: str
    time_exit_rule: str

    environment_fit: bool
    pass_rr: bool
    pass_risk: bool

    approved: bool
    approval_reason: str
