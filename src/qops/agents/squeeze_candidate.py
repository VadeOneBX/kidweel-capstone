"""Squeeze profile specialist (typed tool; no transport authority)."""

from __future__ import annotations

from qops.agents._context import AgentEvaluateContext
from qops.schemas.candidate_memo import (
    MEMO_CLEAN_REJECT,
    MEMO_NO_VIABLE_EXPRESSION,
    MEMO_PASS,
    MEMO_WATCH,
    SqueezeCandidateMemo,
)
from qops.schemas.playbook import AllowedPlaybook

AGENT_NAME = "squeeze_candidate"


def _default_structure(ctx: AgentEvaluateContext) -> str | None:
    if ctx.selected_structure:
        return ctx.selected_structure
    if ctx.structure_bias:
        return ctx.structure_bias
    return AllowedPlaybook.BULL_CALL_SPREAD.value


def evaluate_squeeze_candidate(ctx: AgentEvaluateContext) -> SqueezeCandidateMemo:
    structure = _default_structure(ctx)
    if not ctx.tradeability_pass:
        return SqueezeCandidateMemo(
            candidate_id=ctx.candidate_id,
            agent_name=AGENT_NAME,
            symbol=ctx.symbol,
            source_profile="squeeze",
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
            reason_code="tradeability_fail",
            confidence=0.2,
            source_artifacts=list(ctx.source_artifacts),
            notes=list(ctx.notes) + ["squeeze_tradeability_failed"],
        )

    if ctx.gamma_ratio is None:
        if ctx.watch_viable:
            return SqueezeCandidateMemo(
                candidate_id=ctx.candidate_id,
                agent_name=AGENT_NAME,
                symbol=ctx.symbol,
                source_profile="squeeze",
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
                reason_code="gamma_ratio_absent_watch",
                confidence=0.45,
                source_artifacts=list(ctx.source_artifacts),
                notes=list(ctx.notes) + ["gamma_ratio_absent_operator_review"],
            )
        return SqueezeCandidateMemo(
            candidate_id=ctx.candidate_id,
            agent_name=AGENT_NAME,
            symbol=ctx.symbol,
            source_profile="squeeze",
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
            reason_code="gamma_ratio_absent",
            confidence=0.1,
            source_artifacts=list(ctx.source_artifacts),
            notes=list(ctx.notes),
        )

    if ctx.max_loss is None or ctx.max_loss <= 0:
        return SqueezeCandidateMemo(
            candidate_id=ctx.candidate_id,
            agent_name=AGENT_NAME,
            symbol=ctx.symbol,
            source_profile="squeeze",
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
            reason_code="invalid_max_loss",
            confidence=0.15,
            source_artifacts=list(ctx.source_artifacts),
            notes=list(ctx.notes),
        )

    if ctx.watch_viable:
        return SqueezeCandidateMemo(
            candidate_id=ctx.candidate_id,
            agent_name=AGENT_NAME,
            symbol=ctx.symbol,
            source_profile="squeeze",
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
            reason_code="squeeze_watch_viable",
            confidence=0.55,
            source_artifacts=list(ctx.source_artifacts),
            notes=list(ctx.notes),
        )

    return SqueezeCandidateMemo(
        candidate_id=ctx.candidate_id,
        agent_name=AGENT_NAME,
        symbol=ctx.symbol,
        source_profile="squeeze",
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
        confidence=0.75,
        source_artifacts=list(ctx.source_artifacts),
        notes=list(ctx.notes),
    )


squeeze_candidate_tool = evaluate_squeeze_candidate
