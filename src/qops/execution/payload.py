"""Paper execution payload schema and builder (transport-only, no broker)."""

from __future__ import annotations

import math
from dataclasses import dataclass

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from qops.schemas.risk import TradeEvaluation
from qops.schemas.structure import TradeStructureCandidate


@dataclass(frozen=True, slots=True)
class ExecutionPayload:
    """Immutable execution handoff record for approved paper trades only."""

    symbol: str
    playbook: str
    structure_type: str

    expiry: str

    debit_or_credit: float
    max_profit: float
    max_loss: float

    rr_actual: float
    pmp: float

    tp_rule: str
    sl_rule: str
    time_exit_rule: str

    approved: bool
    approval_reason: str


def _require_non_empty(name: str, value: str) -> None:
    if not value or not str(value).strip():
        raise ValueError(f"{name} must be non-empty")


def _require_positive_finite(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and > 0")


def _require_pmp_range(pmp: float) -> None:
    if not math.isfinite(pmp):
        raise ValueError("pmp must be finite")
    if not (0.0 < pmp < 1.0):
        raise ValueError("pmp must satisfy 0 < pmp < 1")


def build_execution_payload(
    structure: TradeStructureCandidate,
    evaluation: TradeEvaluation,
) -> ExecutionPayload:
    """
    Build execution payload from structure and risk evaluation.

    Must fail if evaluation.approved is False or inputs are incomplete or inconsistent.
    """
    if not evaluation.approved:
        raise ValueError("execution payload requires evaluation.approved is True")

    _require_non_empty("structure.symbol", structure.symbol)
    _require_non_empty("structure.structure_type", structure.structure_type)
    _require_non_empty("structure.expiry", structure.expiry)
    _require_non_empty("evaluation.playbook", evaluation.playbook)
    _require_non_empty("evaluation.tp_rule", evaluation.tp_rule)
    _require_non_empty("evaluation.sl_rule", evaluation.sl_rule)
    _require_non_empty("evaluation.time_exit_rule", evaluation.time_exit_rule)

    if structure.symbol != evaluation.symbol:
        raise ValueError("structure.symbol must match evaluation.symbol")
    if evaluation.playbook != structure.allowed_playbook.value:
        raise ValueError("evaluation.playbook must match structure.allowed_playbook")
    if structure.max_profit != evaluation.max_profit:
        raise ValueError("structure.max_profit must match evaluation.max_profit")
    if structure.max_loss != evaluation.max_loss:
        raise ValueError("structure.max_loss must match evaluation.max_loss")
    if structure.rr_actual != evaluation.rr_actual:
        raise ValueError("structure.rr_actual must match evaluation.rr_actual")

    _require_positive_finite("structure.debit_or_credit", structure.debit_or_credit)
    _require_positive_finite("structure.max_profit", structure.max_profit)
    _require_positive_finite("structure.max_loss", structure.max_loss)
    _require_positive_finite("evaluation.rr_actual", evaluation.rr_actual)
    _require_pmp_range(evaluation.pmp)

    if not math.isfinite(evaluation.rr_required):
        raise ValueError("evaluation.rr_required must be finite")

    return ExecutionPayload(
        symbol=structure.symbol,
        playbook=evaluation.playbook,
        structure_type=structure.structure_type,
        expiry=structure.expiry,
        debit_or_credit=structure.debit_or_credit,
        max_profit=structure.max_profit,
        max_loss=structure.max_loss,
        rr_actual=evaluation.rr_actual,
        pmp=evaluation.pmp,
        tp_rule=evaluation.tp_rule,
        sl_rule=evaluation.sl_rule,
        time_exit_rule=evaluation.time_exit_rule,
        approved=evaluation.approved,
        approval_reason=evaluation.approval_reason,
    )
