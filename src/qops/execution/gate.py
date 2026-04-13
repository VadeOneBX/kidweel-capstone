"""Final paper execution gate before any transport (fail-closed)."""

from __future__ import annotations

import math

from qops.execution.payload import ExecutionPayload


def paper_execution_gate(payload: ExecutionPayload) -> tuple[bool, str]:
    """
    Final safety gate before execution transport.

    Returns (allowed, reason). Any invalid or ambiguous input denies with an explicit reason.
    """
    if not isinstance(payload, ExecutionPayload):
        return False, "invalid_payload_type"

    if not payload.approved:
        return False, "payload_not_approved"

    if not math.isfinite(payload.rr_actual) or payload.rr_actual <= 0.0:
        return False, "invalid_rr_actual"

    if not math.isfinite(payload.pmp) or not (0.0 < payload.pmp < 1.0):
        return False, "invalid_pmp_range"

    if not math.isfinite(payload.max_loss) or payload.max_loss <= 0.0:
        return False, "invalid_max_loss"

    if not math.isfinite(payload.max_profit) or payload.max_profit <= 0.0:
        return False, "invalid_max_profit"

    if not math.isfinite(payload.debit_or_credit) or payload.debit_or_credit <= 0.0:
        return False, "invalid_debit_or_credit"

    if not payload.symbol.strip():
        return False, "missing_symbol"
    if not payload.playbook.strip():
        return False, "missing_playbook"
    if not payload.structure_type.strip():
        return False, "missing_structure_type"
    if not payload.expiry.strip():
        return False, "missing_expiry"

    if not payload.tp_rule.strip() or not payload.sl_rule.strip() or not payload.time_exit_rule.strip():
        return False, "missing_exit_rule"

    return True, "paper_execution_allowed"
