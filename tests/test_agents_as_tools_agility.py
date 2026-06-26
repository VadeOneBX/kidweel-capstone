"""KIDWEEL-PROOF-AGENTS-AS-TOOLS-AGILITY-C1 tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qops.agents._context import AgentEvaluateContext
from qops.agents.coordinator import (
    coordinator_cannot_submit_orders,
    coordinator_evaluate,
    invoke_specialists_as_tools,
    rank_candidate_memos,
    route_memo_through_control_stack,
)
from qops.agents.reverse_vrp_candidate import evaluate_reverse_vrp_candidate
from qops.agents.risk_audit import audit_candidate_memo, promote_watch_to_pass
from qops.agents.squeeze_candidate import evaluate_squeeze_candidate
from qops.agents.vrp_candidate import evaluate_vrp_candidate
from qops.schemas.candidate_memo import (
    MEMO_CLEAN_REJECT,
    MEMO_PASS,
    MEMO_SOURCE_ABSENT,
    MEMO_WATCH,
    CandidateMemo,
)
from qops.schemas.hitl import STATUS_APPROVAL_REQUIRED, STATUS_WATCH_PENDING_REVIEW
from qops.schemas.playbook import AllowedPlaybook

_LEG = {
    "side": "buy",
    "option_type": "CALL",
    "strike": 420.0,
    "expiration": "2026-06-20",
    "quantity": 1,
}
_LEG_SHORT = {
    "side": "sell",
    "option_type": "CALL",
    "strike": 425.0,
    "expiration": "2026-06-20",
    "quantity": 1,
}


def _valid_squeeze_ctx() -> AgentEvaluateContext:
    return AgentEvaluateContext(
        candidate_id="sq-pass-001",
        symbol="SPY",
        source_profile="squeeze",
        regime_label="POSITIVE_GAMMA",
        structure_bias=AllowedPlaybook.BULL_CALL_SPREAD.value,
        selected_structure=AllowedPlaybook.BULL_CALL_SPREAD.value,
        legs=[_LEG, _LEG_SHORT],
        rr_actual=3.5,
        pmp=0.35,
        ev=0.12,
        max_profit=3.95,
        max_loss=1.05,
        gamma_ratio=1.2,
    )


def _valid_vrp_ctx() -> AgentEvaluateContext:
    return AgentEvaluateContext(
        candidate_id="vrp-pass-001",
        symbol="SOFI",
        source_profile="vrp",
        selected_structure=AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value,
        legs=[_LEG, _LEG_SHORT],
        rr_actual=2.1,
        pmp=0.4,
        ev=0.05,
        max_profit=1.2,
        max_loss=0.55,
        vrp=0.08,
    )


def test_coordinator_invokes_two_specialists_as_tools() -> None:
    memos = invoke_specialists_as_tools([_valid_squeeze_ctx(), _valid_vrp_ctx()])
    assert len(memos) == 2
    assert {m.agent_name for m in memos} == {"squeeze_candidate", "vrp_candidate"}
    assert all(isinstance(m, CandidateMemo) for m in memos)


def test_specialist_output_conforms_to_candidate_memo() -> None:
    memo = evaluate_squeeze_candidate(_valid_squeeze_ctx())
    payload = json.loads(memo.model_dump_json())
    assert payload["gate_status"] == MEMO_PASS
    assert payload["agent_name"] == "squeeze_candidate"
    CandidateMemo.model_validate(payload)


def test_coordinator_returns_ranked_list() -> None:
    watch_ctx = AgentEvaluateContext(
        candidate_id="sq-watch-001",
        symbol="SPY",
        source_profile="squeeze",
        legs=[_LEG, _LEG_SHORT],
        max_loss=1.0,
        max_profit=2.0,
        gamma_ratio=1.0,
        watch_viable=True,
    )
    evaluation = coordinator_evaluate([_valid_squeeze_ctx(), watch_ctx])
    assert evaluation.ranked_memos[0].gate_status == MEMO_PASS
    assert evaluation.ranked_memos[1].gate_status == MEMO_WATCH


def test_watch_remains_watch_through_risk_audit() -> None:
    memo = evaluate_squeeze_candidate(
        AgentEvaluateContext(
            candidate_id="w1",
            symbol="SPY",
            source_profile="squeeze",
            legs=[_LEG, _LEG_SHORT],
            max_loss=1.0,
            max_profit=2.0,
            gamma_ratio=1.0,
            watch_viable=True,
        )
    )
    assert memo.gate_status == MEMO_WATCH
    audit = audit_candidate_memo(memo)
    assert audit.gate_status == MEMO_WATCH


def test_clean_reject_remains_clean_reject() -> None:
    memo = evaluate_vrp_candidate(
        AgentEvaluateContext(
            candidate_id="vrp-rej",
            symbol="X",
            source_profile="vrp",
            legs=[_LEG],
            max_loss=1.0,
            vrp=-0.1,
        )
    )
    assert memo.gate_status == MEMO_CLEAN_REJECT
    route = route_memo_through_control_stack(memo, base_dir=Path("/tmp/unused"))
    assert route.paper_submit_allowed is False
    assert route.guardrail_result is None


def test_reverse_vrp_source_absent_when_gamma_missing() -> None:
    memo = evaluate_reverse_vrp_candidate(
        AgentEvaluateContext(
            candidate_id="rvrp-001",
            symbol="SPY",
            source_profile="reverse_vrp",
            legs=[_LEG, _LEG_SHORT],
            max_loss=1.0,
            max_profit=2.0,
            vrp=-0.05,
            gamma_ratio=None,
        )
    )
    assert memo.gate_status == MEMO_SOURCE_ABSENT
    assert "gamma_ratio" in " ".join(memo.notes).lower()


def test_specialists_cannot_submit_orders() -> None:
    assert coordinator_cannot_submit_orders() is True
    with pytest.raises(PermissionError):
        promote_watch_to_pass(
            evaluate_squeeze_candidate(
                AgentEvaluateContext(
                    candidate_id="x",
                    symbol="SPY",
                    source_profile="squeeze",
                    legs=[_LEG],
                    max_loss=1.0,
                    gamma_ratio=1.0,
                    watch_viable=True,
                )
            )
        )


def test_valid_candidate_routes_to_guardrails_then_hitl(tmp_path: Path) -> None:
    memo = evaluate_squeeze_candidate(_valid_squeeze_ctx())
    route = route_memo_through_control_stack(memo, base_dir=tmp_path)
    assert route.guardrail_result is not None
    assert route.guardrail_result.ok is True
    assert route.hitl_route_status == STATUS_APPROVAL_REQUIRED
    assert route.paper_submit_allowed is False


def test_watch_routes_to_hitl_unresolved(tmp_path: Path) -> None:
    memo = evaluate_squeeze_candidate(
        AgentEvaluateContext(
            candidate_id="watch-route",
            symbol="SPY",
            source_profile="squeeze",
            legs=[_LEG, _LEG_SHORT],
            max_loss=1.0,
            max_profit=2.0,
            gamma_ratio=1.0,
            watch_viable=True,
        )
    )
    route = route_memo_through_control_stack(memo, base_dir=tmp_path)
    assert route.hitl_route_status == STATUS_WATCH_PENDING_REVIEW
    assert route.paper_submit_allowed is False


def test_invalid_structure_blocked_before_hitl(tmp_path: Path) -> None:
    memo = evaluate_squeeze_candidate(_valid_squeeze_ctx()).model_copy(
        update={
            "selected_structure": "SHORT_STRANGLE",
            "gate_status": MEMO_PASS,
        }
    )
    route = route_memo_through_control_stack(memo, base_dir=tmp_path)
    assert route.hitl_route_status is None
    assert route.risk_audit.gate_status == MEMO_CLEAN_REJECT
    assert route.guardrail_result is None


def test_example_typed_candidate_memo_json() -> None:
    memo = evaluate_squeeze_candidate(_valid_squeeze_ctx())
    example = json.loads(memo.model_dump_json())
    assert example["symbol"] == "SPY"
    assert example["gate_status"] == "PASS"
    assert example["max_loss"] == 1.05
