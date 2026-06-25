"""Post-ORB Tier 3 subagent idea artifacts (AGENT-SKILLS-C2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

IdeaType = Literal["PROPOSE", "WATCH", "PASS"]

TIER3_AGENTS: tuple[str, ...] = (
    "squeeze-candidates",
    "volatility-risk-premium",
    "reverse-risk-premium",
)

AGENT_IDEA_SOURCE: dict[str, str] = {
    "squeeze-candidates": "squeeze",
    "volatility-risk-premium": "vrp",
    "reverse-risk-premium": "reverse-vrp",
}


class SubagentIdea(BaseModel):
    idea_type: IdeaType
    symbol: str
    source: str
    data_basis: dict[str, object] = Field(default_factory=dict)
    reason: str = ""

    @field_validator("source")
    @classmethod
    def source_non_empty(cls, v: str) -> str:
        if not str(v).strip():
            raise ValueError("source_required")
        return str(v).strip()

    @field_validator("data_basis")
    @classmethod
    def data_basis_non_empty(cls, v: dict[str, object]) -> dict[str, object]:
        if not v:
            raise ValueError("data_basis_required")
        return v


class SubagentIdeasArtifact(BaseModel):
    run_id: str
    agent_id: str
    idea_source: str
    ideas: list[SubagentIdea]

    @field_validator("ideas")
    @classmethod
    def exactly_three_ideas(cls, v: list[SubagentIdea]) -> list[SubagentIdea]:
        if len(v) != 3:
            raise ValueError(f"expected_exactly_three_ideas got={len(v)}")
        return v


def ideas_artifact_path(base_dir: Path, run_date: str, run_id: str, agent_id: str) -> Path:
    return base_dir / "data" / "runs" / run_date / f"{run_id}_{agent_id}_ideas.json"


def load_tier3_ideas(
    base_dir: Path,
    run_date: str,
    run_id: str,
) -> list[SubagentIdeasArtifact]:
    loaded: list[SubagentIdeasArtifact] = []
    for agent_id in TIER3_AGENTS:
        path = ideas_artifact_path(base_dir, run_date, run_id, agent_id)
        if not path.is_file():
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        artifact = SubagentIdeasArtifact.model_validate(raw)
        expected_source = AGENT_IDEA_SOURCE[agent_id]
        if artifact.idea_source != expected_source:
            raise ValueError(f"idea_source_mismatch agent={agent_id}")
        if artifact.agent_id != agent_id:
            raise ValueError(f"agent_id_mismatch path={path}")
        loaded.append(artifact)
    return loaded


def validate_ideas_for_distillation(artifacts: list[SubagentIdeasArtifact]) -> None:
    """Raise if any idea lacks source or data basis (stop condition)."""
    for artifact in artifacts:
        for idx, idea in enumerate(artifact.ideas):
            if not idea.source.strip():
                raise RuntimeError(
                    f"IDEA_DISTILLATION_BLOCKED_MISSING_SOURCE:"
                    f"agent={artifact.agent_id} index={idx}"
                )
            if not idea.data_basis:
                raise RuntimeError(
                    f"IDEA_DISTILLATION_BLOCKED_MISSING_DATA_BASIS:"
                    f"agent={artifact.agent_id} index={idx}"
                )


def count_idea_types(artifacts: list[SubagentIdeasArtifact]) -> dict[str, int]:
    counts = {"PROPOSE": 0, "WATCH": 0, "PASS": 0}
    for artifact in artifacts:
        for idea in artifact.ideas:
            counts[idea.idea_type] = counts.get(idea.idea_type, 0) + 1
    return counts
