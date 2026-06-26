"""Coordinator: invoke specialists, rank memos, route to guardrails/HITL (no submit)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qops.agents._context import AgentEvaluateContext
from qops.agents.reverse_vrp_candidate import evaluate_reverse_vrp_candidate
from qops.agents.risk_audit import RiskAuditResult, audit_candidate_memo
from qops.agents.squeeze_candidate import evaluate_squeeze_candidate
from qops.agents.vrp_candidate import evaluate_vrp_candidate
from qops.guardrails.base import GuardrailCandidate, GuardrailResult, evaluate_guardrails
from qops.schemas.candidate_memo import (
    MEMO_CLEAN_REJECT,
    MEMO_NO_VIABLE_EXPRESSION,
    MEMO_PASS,
    MEMO_SOURCE_ABSENT,
    MEMO_WATCH,
    CandidateMemo,
)
from qops.schemas.hitl import STATUS_APPROVAL_REQUIRED, STATUS_WATCH_PENDING_REVIEW

SpecialistTool = Callable[[AgentEvaluateContext], CandidateMemo]

_PROFILE_TOOLS: dict[str, SpecialistTool] = {
    "squeeze": evaluate_squeeze_candidate,
    "vrp": evaluate_vrp_candidate,
    "reverse_vrp": evaluate_reverse_vrp_candidate,
}

_RANK_ORDER: dict[str, int] = {
    MEMO_PASS: 0,
    MEMO_WATCH: 1,
    MEMO_NO_VIABLE_EXPRESSION: 2,
    MEMO_SOURCE_ABSENT: 3,
    MEMO_CLEAN_REJECT: 4,
}


@dataclass(frozen=True, slots=True)
class CoordinatorEvaluation:
    ranked_memos: tuple[CandidateMemo, ...]
    specialist_outputs: tuple[CandidateMemo, ...]
    transport_submit_allowed: bool = False


@dataclass(frozen=True, slots=True)
class ControlStackRoute:
    memo: CandidateMemo
    risk_audit: RiskAuditResult
    guardrail_result: GuardrailResult | None
    hitl_route_status: str | None
    paper_submit_allowed: bool
    trace: list[str] = field(default_factory=list)


def specialist_tools_for_profile(source_profile: str) -> SpecialistTool | None:
    return _PROFILE_TOOLS.get(source_profile.strip().lower())


def invoke_specialist_tool(ctx: AgentEvaluateContext) -> CandidateMemo:
    tool = specialist_tools_for_profile(ctx.source_profile)
    if tool is None:
        return CandidateMemo(
            candidate_id=ctx.candidate_id,
            agent_name="coordinator",
            symbol=ctx.symbol,
            source_profile=ctx.source_profile,
            regime_label=ctx.regime_label,
            structure_bias=ctx.structure_bias,
            selected_structure=ctx.selected_structure,
            legs=list(ctx.legs),
            rr_actual=ctx.rr_actual,
            pmp=ctx.pmp,
            ev=ctx.ev,
            max_profit=ctx.max_profit,
            max_loss=ctx.max_loss,
            gate_status=MEMO_CLEAN_REJECT,
            reason_code="unknown_source_profile",
            confidence=None,
            source_artifacts=list(ctx.source_artifacts),
            notes=list(ctx.notes),
        )
    return tool(ctx)


def invoke_specialists_as_tools(
    contexts: Sequence[AgentEvaluateContext],
) -> list[CandidateMemo]:
    return [invoke_specialist_tool(ctx) for ctx in contexts]


def rank_candidate_memos(memos: Sequence[CandidateMemo]) -> list[CandidateMemo]:
    return sorted(
        memos,
        key=lambda m: (
            _RANK_ORDER.get(m.gate_status, 99),
            -(m.confidence or 0.0),
            m.candidate_id,
        ),
    )


def coordinator_evaluate(contexts: Sequence[AgentEvaluateContext]) -> CoordinatorEvaluation:
    outputs = invoke_specialists_as_tools(contexts)
    ranked = rank_candidate_memos(outputs)
    return CoordinatorEvaluation(
        ranked_memos=tuple(ranked),
        specialist_outputs=tuple(outputs),
        transport_submit_allowed=False,
    )


def guardrail_candidate_from_memo(memo: CandidateMemo) -> GuardrailCandidate:
    watch = memo.gate_status == MEMO_WATCH
    return GuardrailCandidate(
        candidate_id=memo.candidate_id,
        symbol=memo.symbol,
        structure=memo.selected_structure or "",
        legs=list(memo.legs),
        max_loss=memo.max_loss,
        max_profit=memo.max_profit,
        rr_actual=memo.rr_actual,
        pmp=memo.pmp,
        ev=memo.ev,
        watch_promotion_viable=watch,
    )


def route_memo_through_control_stack(
    memo: CandidateMemo,
    *,
    base_dir: Path | None = None,
) -> ControlStackRoute:
    """Risk audit → guardrails → HITL route status (no broker submission)."""
    trace: list[str] = ["coordinator:route_control_stack"]
    audit = audit_candidate_memo(memo)
    memo_after_audit = audit.memo
    trace.append(f"risk_audit:{audit.gate_status}")

    if audit.gate_status in {MEMO_CLEAN_REJECT, MEMO_NO_VIABLE_EXPRESSION, MEMO_SOURCE_ABSENT}:
        return ControlStackRoute(
            memo=memo_after_audit,
            risk_audit=audit,
            guardrail_result=None,
            hitl_route_status=None,
            paper_submit_allowed=False,
            trace=trace,
        )

    if audit.gate_status == MEMO_WATCH:
        guard = evaluate_guardrails(
            guardrail_candidate_from_memo(memo_after_audit),
            base_dir=base_dir,
            write_audit=True,
        )
        trace.append(f"guardrails:{guard.status}")
        return ControlStackRoute(
            memo=memo_after_audit,
            risk_audit=audit,
            guardrail_result=guard,
            hitl_route_status=STATUS_WATCH_PENDING_REVIEW,
            paper_submit_allowed=False,
            trace=trace,
        )

    guard = evaluate_guardrails(
        guardrail_candidate_from_memo(memo_after_audit),
        base_dir=base_dir,
        write_audit=False,
    )
    trace.append(f"guardrails:{guard.status}")
    if not guard.ok:
        return ControlStackRoute(
            memo=memo_after_audit,
            risk_audit=audit,
            guardrail_result=guard,
            hitl_route_status=None,
            paper_submit_allowed=False,
            trace=trace,
        )

    return ControlStackRoute(
        memo=memo_after_audit,
        risk_audit=audit,
        guardrail_result=guard,
        hitl_route_status=STATUS_APPROVAL_REQUIRED,
        paper_submit_allowed=False,
        trace=trace,
    )


def try_openai_agents_tool_wrapper(tool: SpecialistTool) -> SpecialistTool:
    """Optional SDK hook; repo-local callable remains canonical."""
    try:
        import agents  # type: ignore[import-not-found]  # noqa: F401
    except ImportError:
        return tool
    return tool


def coordinator_cannot_submit_orders() -> bool:
    return True
