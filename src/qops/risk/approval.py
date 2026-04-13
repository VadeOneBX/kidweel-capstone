"""Deterministic trade-structure risk approval."""

from __future__ import annotations

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from qops.risk.rr_audit import audit_structure_rr
from qops.schemas.risk import TradeEvaluation
from qops.schemas.structure import TradeStructureCandidate


def evaluate_trade_structure(
    structure: TradeStructureCandidate,
    pmp: float,
    environment_fit: bool,
    tp_rule: str = "TP_80",
    sl_rule: str = "STOP",
    time_exit_rule_name: str = "TIME_EXIT",
) -> TradeEvaluation:
    """Return a deterministic trade evaluation from structure, PMP, and environment fit."""
    pass_rr, rr_required, rr_actual, rr_reason = audit_structure_rr(structure=structure, pmp=pmp)

    if rr_reason == "invalid_pmp":
        approval_reason = "invalid_input:invalid_pmp"
    elif rr_reason == "invalid_rr":
        approval_reason = "invalid_input:invalid_rr"
    elif pass_rr and environment_fit:
        approval_reason = "approved"
    elif (not pass_rr) and (not environment_fit):
        approval_reason = "both_failed"
    elif not pass_rr:
        approval_reason = "rr_insufficient"
    else:
        approval_reason = "environment_mismatch"

    pass_risk = pass_rr and environment_fit
    approved = pass_risk

    return TradeEvaluation(
        symbol=structure.symbol,
        playbook=structure.allowed_playbook.value,
        pmp=pmp,
        rr_required=rr_required,
        rr_actual=rr_actual,
        max_profit=structure.max_profit,
        max_loss=structure.max_loss,
        tp_rule=tp_rule,
        sl_rule=sl_rule,
        time_exit_rule=time_exit_rule_name,
        environment_fit=environment_fit,
        pass_rr=pass_rr,
        pass_risk=pass_risk,
        approved=approved,
        approval_reason=approval_reason,
    )
