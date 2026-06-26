"""Reverse-VRP profile specialist (typed tool; no transport authority)."""

from __future__ import annotations

from qops.agents._context import AgentEvaluateContext
from qops.schemas.candidate_memo import (
    MEMO_CLEAN_REJECT,
    MEMO_PASS,
    MEMO_SOURCE_ABSENT,
    MEMO_WATCH,
    ReverseVRPCandidateMemo,
)
from qops.schemas.playbook import AllowedPlaybook

AGENT_NAME = "reverse_vrp_candidate"


def evaluate_reverse_vrp_candidate(ctx: AgentEvaluateContext) -> ReverseVRPCandidateMemo:
    structure = ctx.selected_structure or AllowedPlaybook.BULL_CALL_SPREAD.value

    if ctx.gamma_ratio is None:
        return ReverseVRPCandidateMemo(
            candidate_id=ctx.candidate_id,
            agent_name=AGENT_NAME,
            symbol=ctx.symbol,
            source_profile="reverse_vrp",
            regime_label=ctx.regime_label,
            structure_bias=ctx.structure_bias,
            selected_structure=structure,
            legs=list(ctx.legs),
            rr_actual=ctx.rr_actual,
            pmp=ctx.pmp,
            ev=ctx.ev,
            max_profit=ctx.max_profit,
            max_loss=ctx.max_loss,
            gate_status=MEMO_SOURCE_ABSENT,
            reason_code="gamma_ratio_absent",
            confidence=None,
            source_artifacts=list(ctx.source_artifacts),
            notes=list(ctx.notes)
            + [
                "gamma_ratio absent from source export; reverse_vrp scoring limited to iv/rv context"
            ],
        )

    if ctx.vrp is not None and ctx.vrp >= 0:
        return ReverseVRPCandidateMemo(
            candidate_id=ctx.candidate_id,
            agent_name=AGENT_NAME,
            symbol=ctx.symbol,
            source_profile="reverse_vrp",
            regime_label=ctx.regime_label,
            structure_bias=ctx.structure_bias,
            selected_structure=structure,
            legs=list(ctx.legs),
            rr_actual=ctx.rr_actual,
            pmp=ctx.pmp,
            ev=ctx.ev,
            max_profit=ctx.max_profit,
            max_loss=ctx.max_loss,
            gate_status=MEMO_CLEAN_REJECT,
            reason_code="vrp_not_negative",
            confidence=0.2,
            source_artifacts=list(ctx.source_artifacts),
            notes=list(ctx.notes),
        )

    if ctx.watch_viable:
        return ReverseVRPCandidateMemo(
            candidate_id=ctx.candidate_id,
            agent_name=AGENT_NAME,
            symbol=ctx.symbol,
            source_profile="reverse_vrp",
            regime_label=ctx.regime_label,
            structure_bias=ctx.structure_bias,
            selected_structure=structure,
            legs=list(ctx.legs),
            rr_actual=ctx.rr_actual,
            pmp=ctx.pmp,
            ev=ctx.ev,
            max_profit=ctx.max_profit,
            max_loss=ctx.max_loss,
            gate_status=MEMO_WATCH,
            reason_code="reverse_vrp_watch",
            confidence=0.5,
            source_artifacts=list(ctx.source_artifacts),
            notes=list(ctx.notes),
        )

    return ReverseVRPCandidateMemo(
        candidate_id=ctx.candidate_id,
        agent_name=AGENT_NAME,
        symbol=ctx.symbol,
        source_profile="reverse_vrp",
        regime_label=ctx.regime_label,
        structure_bias=ctx.structure_bias,
        selected_structure=structure,
        legs=list(ctx.legs),
        rr_actual=ctx.rr_actual,
        pmp=ctx.pmp,
        ev=ctx.ev,
        max_profit=ctx.max_profit,
        max_loss=ctx.max_loss,
        gate_status=MEMO_PASS,
        reason_code=None,
        confidence=0.65,
        source_artifacts=list(ctx.source_artifacts),
        notes=list(ctx.notes),
    )


reverse_vrp_candidate_tool = evaluate_reverse_vrp_candidate
