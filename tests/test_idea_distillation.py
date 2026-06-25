"""Tests for AGENT-SKILLS-C2 idea distillation."""

from __future__ import annotations

import json
from pathlib import Path

from qops.advisory.idea_distillation import distill_subagent_ideas
from qops.advisory.subagent_ideas import SubagentIdeasArtifact
from qops.schemas.playbook import AllowedPlaybook


def _idea(
    idea_type: str,
    symbol: str,
    *,
    pop: float | None = None,
    bias: str = "bullish",
) -> dict:
    basis: dict = {
        "directional_bias": bias,
        "source_panel": "context_artifact",
    }
    if pop is not None:
        basis.update(
            {
                "structure_type": AllowedPlaybook.BULL_CALL_SPREAD.value,
                "spread_width": 5.0,
                "net_debit": 1.0,
                "reference_strike": 100.0,
                "probability_of_profit": pop,
            }
        )
    return {
        "idea_type": idea_type,
        "symbol": symbol,
        "source": "data/processed/mock_sg_context.csv",
        "data_basis": basis,
        "reason": "test",
    }


def _artifact(agent_id: str, idea_source: str, ideas: list[dict]) -> SubagentIdeasArtifact:
    return SubagentIdeasArtifact.model_validate(
        {
            "run_id": "test-run",
            "agent_id": agent_id,
            "idea_source": idea_source,
            "ideas": ideas,
        }
    )


def test_missing_source_blocks_distillation() -> None:
    artifact = _artifact(
        "squeeze-candidates",
        "squeeze",
        [
            _idea("PROPOSE", "AAPL"),
            _idea("WATCH", "AAPL"),
            _idea("PASS", "AAPL"),
        ],
    )
    artifact.ideas[0].source = ""
    result = distill_subagent_ideas([artifact])
    assert result.blocked
    assert "MISSING_SOURCE" in result.block_reason


def test_negative_ev_forces_pass() -> None:
    artifact = _artifact(
        "reverse-risk-premium",
        "reverse-vrp",
        [
            _idea("PROPOSE", "AAPL", pop=0.01),
            _idea("WATCH", "AAPL", pop=0.5),
            _idea("PASS", "MSFT"),
        ],
    )
    result = distill_subagent_ideas([artifact], regime_label="NEUTRAL")
    propose_votes = [v for v in result.votes if v.idea_type == "PROPOSE"]
    assert propose_votes
    assert propose_votes[0].vote == "PASS"
    assert propose_votes[0].ev_check in {"NEGATIVE", "MISSING_DATA"}


def test_positive_ev_allows_propose() -> None:
    artifact = _artifact(
        "squeeze-candidates",
        "squeeze",
        [
            _idea("PROPOSE", "AAPL", pop=0.65),
            _idea("WATCH", "MSFT", pop=0.65),
            _idea("PASS", "GOOG"),
        ],
    )
    result = distill_subagent_ideas([artifact], regime_label="SQUEEZE_UP")
    top = result.votes[0]
    assert top.vote == "PROPOSE"
    assert top.ev_check == "POSITIVE"
    assert top.rec_structure


def test_agent_signal_weak_when_all_pass() -> None:
    artifact = _artifact(
        "volatility-risk-premium",
        "vrp",
        [
            _idea("PROPOSE", "AAPL"),
            _idea("WATCH", "MSFT"),
            _idea("PASS", "GOOG"),
        ],
    )
    result = distill_subagent_ideas([artifact])
    assert "AGENT_SIGNAL_WEAK:volatility-risk-premium" in result.agent_signal_weak


def test_ideas_artifact_round_trip(tmp_path: Path) -> None:
    from qops.advisory.subagent_ideas import ideas_artifact_path, load_tier3_ideas

    run_date = "2026-06-24"
    run_id = "manual-test"
    agent = "squeeze-candidates"
    path = ideas_artifact_path(tmp_path, run_date, run_id, agent)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "agent_id": agent,
        "idea_source": "squeeze",
        "ideas": [
            _idea("WATCH", "AAPL"),
            _idea("PASS", "MSFT"),
            _idea("PASS", "GOOG"),
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = load_tier3_ideas(tmp_path, run_date, run_id)
    assert len(loaded) == 1
    assert len(loaded[0].ideas) == 3
