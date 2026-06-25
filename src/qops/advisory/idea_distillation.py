"""Deterministic distillation of Tier 3 post-ORB ideas (AGENT-SKILLS-C2)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field

from qops.advisory.subagent_ideas import (
    SubagentIdea,
    SubagentIdeasArtifact,
    validate_ideas_for_distillation,
)
from qops.schemas.environment import RegimeLabel
from qops.schemas.playbook import AllowedPlaybook
from qops.strategy.spread_math import SpreadMathInputs, evaluate_spread_math

RegimeAlignment = Literal["ALIGNED", "CONTRADICTS", "NEUTRAL"]
EvCheck = Literal["POSITIVE", "NEGATIVE", "MISSING_DATA"]
DistillVote = Literal["PROPOSE", "WATCH", "PASS"]
DealerTier = Literal["A", "B", "C", "D", "E", "NOT_SCORED"]


class PolicyVote(BaseModel):
    symbol: str
    idea_source: str
    idea_type: str
    data_basis: dict[str, object] = Field(default_factory=dict)
    regime_alignment: RegimeAlignment
    ev_check: EvCheck
    dealer_tier: DealerTier
    vote: DistillVote
    vote_reason: str
    rec_structure: str = ""
    agreement_count: int = 1


class IdeaDistillationResult(BaseModel):
    votes: list[PolicyVote] = Field(default_factory=list)
    agent_signal_weak: list[str] = Field(default_factory=list)
    blocked: bool = False
    block_reason: str = ""


@dataclass(frozen=True, slots=True)
class _ConsolidatedIdea:
    symbol: str
    idea_source: str
    idea_type: str
    data_basis: dict[str, object]
    reason: str
    agreement_count: int


def _directional_thesis(data_basis: dict[str, object]) -> str:
    for key in ("directional_bias", "directional_thesis", "skew_signal"):
        val = data_basis.get(key)
        if val is not None and str(val).strip():
            return str(val).strip().lower()
    return ""


def _consolidate_ideas(artifacts: list[SubagentIdeasArtifact]) -> list[_ConsolidatedIdea]:
    buckets: dict[tuple[str, str, str], list[SubagentIdea]] = {}
    source_by_agent = {a.agent_id: a.idea_source for a in artifacts}

    for artifact in artifacts:
        for idea in artifact.ideas:
            sym = idea.symbol.strip().upper()
            thesis = _directional_thesis(idea.data_basis)
            key = (sym, thesis, artifact.idea_source)
            buckets.setdefault(key, []).append(idea)

    consolidated: list[_ConsolidatedIdea] = []
    for (sym, _thesis, idea_source), ideas in buckets.items():
        primary = ideas[0]
        agent_source = idea_source
        merged_basis = dict(primary.data_basis)
        consolidated.append(
            _ConsolidatedIdea(
                symbol=sym,
                idea_source=agent_source,
                idea_type=primary.idea_type,
                data_basis=merged_basis,
                reason=primary.reason,
                agreement_count=len(ideas),
            )
        )
    return consolidated


def _regime_alignment(regime: str, data_basis: dict[str, object]) -> RegimeAlignment:
    regime_u = (regime or "").strip().upper()
    bias = _directional_thesis(data_basis)
    if not regime_u or regime_u == RegimeLabel.NEUTRAL.value:
        return "NEUTRAL"
    if not bias:
        return "NEUTRAL"

    bullish = any(x in bias for x in ("bull", "up", "long", "call"))
    bearish = any(x in bias for x in ("bear", "down", "short", "put", "credit"))

    if regime_u in {RegimeLabel.SQUEEZE_UP.value, RegimeLabel.BUY_PREMIUM.value}:
        if bearish and not bullish:
            return "CONTRADICTS"
        if bullish:
            return "ALIGNED"
    if regime_u == RegimeLabel.SELL_PREMIUM.value:
        if bullish and not bearish:
            return "CONTRADICTS"
        if bearish or "credit" in bias:
            return "ALIGNED"
    return "NEUTRAL"


def _run_ev_check(data_basis: dict[str, object]) -> tuple[EvCheck, str, bool]:
    """Return ev_check, rec_structure hint, ev_positive."""
    required = ("structure_type", "spread_width", "net_debit", "reference_strike")
    if not all(k in data_basis for k in required):
        return "MISSING_DATA", "", False

    pop = data_basis.get("probability_of_profit")
    if pop is None:
        return "MISSING_DATA", "probability_of_profit_required_for_ev", False

    try:
        structure = str(data_basis["structure_type"])
        width = float(data_basis["spread_width"])
        debit = float(data_basis["net_debit"])
        strike = float(data_basis["reference_strike"])
        p = float(pop)
    except (TypeError, ValueError):
        return "MISSING_DATA", "ev_inputs_invalid", False

    if structure not in {
        AllowedPlaybook.BULL_CALL_SPREAD.value,
        AllowedPlaybook.BEAR_PUT_SPREAD.value,
    }:
        return "MISSING_DATA", "debit_spread_required_for_ev_filter", False

    try:
        evaluation = evaluate_spread_math(
            SpreadMathInputs(
                structure_type=structure,
                spread_width=width,
                net_debit_or_credit=debit,
                reference_strike=strike,
            ),
            probability_of_profit=p,
        )
    except (ValueError, RuntimeError) as exc:
        return "MISSING_DATA", f"ev_calculator_error:{exc!s}", False

    if evaluation.pass_ev and evaluation.expected_value is not None and evaluation.expected_value > 0:
        rec = f"{structure} width={width} debit={debit}"
        return "POSITIVE", rec, True
    if evaluation.expected_value is not None and math.isfinite(evaluation.expected_value):
        return "NEGATIVE", "non_positive_expected_value", False
    return "MISSING_DATA", "ev_incomplete", False


def _dealer_tier_for_symbol(expressions_df: pd.DataFrame, symbol: str) -> DealerTier:
    if expressions_df.empty or "symbol" not in expressions_df.columns:
        return "NOT_SCORED"
    sym = symbol.strip().upper()
    rows = expressions_df[expressions_df["symbol"].astype(str).str.upper() == sym]
    if rows.empty:
        return "NOT_SCORED"
    tier_col = "dealer_tier" if "dealer_tier" in rows.columns else None
    if not tier_col:
        return "NOT_SCORED"
    raw = str(rows.iloc[0].get(tier_col, "") or "").strip().upper()
    if raw in {"A", "B", "C", "D", "E"}:
        return raw  # type: ignore[return-value]
    return "NOT_SCORED"


def _confidence_for_symbol(context_df: pd.DataFrame, symbol: str) -> float:
    if context_df.empty or "symbol" not in context_df.columns:
        return 0.0
    sym = symbol.strip().upper()
    rows = context_df[context_df["symbol"].astype(str).str.upper() == sym]
    if rows.empty or "confidence" not in rows.columns:
        return 0.0
    try:
        return float(rows.iloc[0]["confidence"])
    except (TypeError, ValueError):
        return 0.0


_TIER_RANK = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1, "NOT_SCORED": 0}


def _rank_key(
    vote: PolicyVote,
    *,
    expressions_df: pd.DataFrame,
    context_df: pd.DataFrame,
) -> tuple[int, float, int]:
    tier = vote.dealer_tier
    if tier == "NOT_SCORED":
        tier = _dealer_tier_for_symbol(expressions_df, vote.symbol)
    conf = _confidence_for_symbol(context_df, vote.symbol)
    return (_TIER_RANK.get(tier, 0), conf, vote.agreement_count)


def _final_vote(
    idea_type: str,
    ev_check: EvCheck,
    regime_alignment: RegimeAlignment,
    ev_positive: bool,
) -> DistillVote:
    if ev_check in {"NEGATIVE", "MISSING_DATA"}:
        return "PASS"
    if regime_alignment == "CONTRADICTS":
        return "WATCH" if idea_type == "PROPOSE" else "PASS"
    if idea_type == "PASS":
        return "PASS"
    if idea_type == "WATCH":
        return "WATCH" if ev_positive else "PASS"
    if idea_type == "PROPOSE" and ev_positive:
        return "PROPOSE"
    return "PASS"


def distill_subagent_ideas(
    artifacts: list[SubagentIdeasArtifact],
    *,
    regime_label: str = "",
    context_df: pd.DataFrame | None = None,
    expressions_df: pd.DataFrame | None = None,
) -> IdeaDistillationResult:
    if not artifacts:
        return IdeaDistillationResult()

    try:
        validate_ideas_for_distillation(artifacts)
    except RuntimeError as exc:
        return IdeaDistillationResult(blocked=True, block_reason=str(exc))

    ctx = context_df if context_df is not None else pd.DataFrame()
    expr = expressions_df if expressions_df is not None else pd.DataFrame()

    consolidated = _consolidate_ideas(artifacts)
    votes: list[PolicyVote] = []

    for item in consolidated:
        alignment = _regime_alignment(regime_label, item.data_basis)
        ev_check, ev_detail, ev_positive = _run_ev_check(item.data_basis)
        tier = _dealer_tier_for_symbol(expr, item.symbol)
        vote_label = _final_vote(item.idea_type, ev_check, alignment, ev_positive)

        reason_parts: list[str] = []
        if item.reason:
            reason_parts.append(item.reason)
        if ev_check == "MISSING_DATA":
            reason_parts.append(ev_detail or "ev_data_missing")
        elif ev_check == "NEGATIVE":
            reason_parts.append("negative_ev_at_stated_width")
        if alignment == "CONTRADICTS":
            reason_parts.append("contradicts_regime_context")
        if item.agreement_count > 1:
            reason_parts.append(f"agreement_count={item.agreement_count}")
        if not reason_parts:
            reason_parts.append("distilled_ok")

        rec = ""
        if vote_label == "PROPOSE" and ev_positive:
            _, rec, _ = _run_ev_check(item.data_basis)

        votes.append(
            PolicyVote(
                symbol=item.symbol,
                idea_source=item.idea_source,
                idea_type=item.idea_type,
                data_basis=item.data_basis,
                regime_alignment=alignment,
                ev_check=ev_check,
                dealer_tier=tier,
                vote=vote_label,
                vote_reason="; ".join(reason_parts),
                rec_structure=rec,
                agreement_count=item.agreement_count,
            )
        )

    votes.sort(
        key=lambda v: _rank_key(v, expressions_df=expr, context_df=ctx),
        reverse=True,
    )

    weak: list[str] = []
    for artifact in artifacts:
        per_idea_votes: list[DistillVote] = []
        for idea in artifact.ideas:
            alignment = _regime_alignment(regime_label, idea.data_basis)
            ev_check, _, ev_positive = _run_ev_check(idea.data_basis)
            per_idea_votes.append(
                _final_vote(idea.idea_type, ev_check, alignment, ev_positive)
            )
        if len(per_idea_votes) == 3 and all(v == "PASS" for v in per_idea_votes):
            weak.append(f"AGENT_SIGNAL_WEAK:{artifact.agent_id}")

    return IdeaDistillationResult(votes=votes, agent_signal_weak=weak)


def format_policy_votes_section(result: IdeaDistillationResult) -> str:
    if result.blocked:
        return f"**Idea distillation blocked:** `{result.block_reason}`\n"
    if not result.votes:
        return "_No Tier 3 idea artifacts found for this run._\n"

    lines = ["## Post-ORB idea distillation (policy votes)", ""]
    if result.agent_signal_weak:
        for flag in result.agent_signal_weak:
            lines.append(f"- Coordinator flag: `{flag}`")
        lines.append("")

    for idx, vote in enumerate(result.votes, start=1):
        lines.append(f"### Rank {idx} — `{vote.symbol}`")
        lines.append(f"idea_source: {vote.idea_source}")
        lines.append(f"idea_type: {vote.idea_type}")
        lines.append(f"regime_alignment: {vote.regime_alignment}")
        lines.append(f"ev_check: {vote.ev_check}")
        lines.append(f"dealer_tier: {vote.dealer_tier}")
        lines.append(f"vote: {vote.vote}")
        lines.append(f"vote_reason: {vote.vote_reason}")
        if vote.rec_structure:
            lines.append(f"rec_structure: {vote.rec_structure}")
        if vote.agreement_count > 1:
            lines.append(f"agreement_count: {vote.agreement_count}")
        lines.append("")

    return "\n".join(lines)
