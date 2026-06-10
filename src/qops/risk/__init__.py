"""Deterministic risk policy helpers for PMP, RR audit, exits, and approval."""

from __future__ import annotations

from qops.risk.approval import evaluate_trade_structure
from qops.risk.exits import debit_stop_loss, take_profit_target, time_exit_rule
from qops.risk.pmp_policy import (
    PMP_TO_MIN_RR,
    min_rr_for_pmp,
    normalize_pmp_bucket,
    passes_pmp_rr_gate,
    required_rr_from_pmp,
    validate_pmp,
)
from qops.risk.rr_audit import audit_structure_rr, rr_is_sufficient

__all__ = [
    "audit_structure_rr",
    "debit_stop_loss",
    "evaluate_trade_structure",
    "PMP_TO_MIN_RR",
    "min_rr_for_pmp",
    "normalize_pmp_bucket",
    "passes_pmp_rr_gate",
    "required_rr_from_pmp",
    "rr_is_sufficient",
    "take_profit_target",
    "time_exit_rule",
    "validate_pmp",
]
