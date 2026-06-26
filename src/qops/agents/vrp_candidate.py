"""VRP profile specialist (typed tool; no transport authority)."""

from __future__ import annotations

from qops.agents._context import AgentEvaluateContext
from qops.schemas.candidate_memo import (
    MEMO_CLEAN_REJECT,
    MEMO_NO_VIABLE_EXPRESSION,
    MEMO_PASS,
    MEMO_WATCH,
    VRPCandidateMemo,
)
from qops.schemas.playbook import AllowedPlaybook

AGENT_NAME = "vrp_candidate"


def evaluate_vrp_candidate(ctx: AgentEvaluateContext) -> VRPCandidateMemo:
    structure = ctx.selected_structure or AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value

    if ctx.vrp is not None and ctx.vrp <= 0:
        return VRPCandidateMemo(
            candidate_id=ctx.candidate_id,
            agent_name=AGENT_NAME,
            symbol=ctx.symbol,
            source_profile="vrp",
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
            reason_code="vrp_not_rich",
            confidence=0.2,
            source_artifacts=list(ctx.source_artifacts),
            notes=list(ctx.notes) + ["vrp_not_positive"],
        )

    if not ctx.legs or ctx.max_loss is None:
        return VRPCandidateMemo(
            candidate_id=ctx.candidate_id,
            agent_name=AGENT_NAME,
            symbol=ctx.symbol,
            source_profile="vrp",
            regime_label=ctx.regime_label,
            structure_bias=ctx.structure_bias,
            selected_structure=structure,
            legs=list(ctx.legs),
            rr_actual=ctx.rr_actual,
            pmp=ctx.pmp,
            ev=ctx.ev,
            max_profit=ctx.max_profit,
            max_loss=ctx.max_loss,
            gate_status=MEMO_NO_VIABLE_EXPRESSION,
            reason_code="incomplete_vrp_expression",
            confidence=0.25,
            source_artifacts=list(ctx.source_artifacts),
            notes=list(ctx.notes),
        )

    if ctx.watch_viable:
        return VRPCandidateMemo(
            candidate_id=ctx.candidate_id,
            agent_name=AGENT_NAME,
            symbol=ctx.symbol,
            source_profile="vrp",
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
            reason_code="vrp_watch_viable",
            confidence=0.5,
            source_artifacts=list(ctx.source_artifacts),
            notes=list(ctx.notes),
        )

    return VRPCandidateMemo(
        candidate_id=ctx.candidate_id,
        agent_name=AGENT_NAME,
        symbol=ctx.symbol,
        source_profile="vrp",
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
        confidence=0.7,
        source_artifacts=list(ctx.source_artifacts),
        notes=list(ctx.notes),
    )


vrp_candidate_tool = evaluate_vrp_candidate
