"""Typed specialist agent outputs (KIDWEEL-PROOF-AGENTS-AS-TOOLS-AGILITY-C1)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

MEMO_PASS = "PASS"
MEMO_WATCH = "WATCH"
MEMO_CLEAN_REJECT = "CLEAN_REJECT"
MEMO_NO_VIABLE_EXPRESSION = "NO_VIABLE_EXPRESSION"
MEMO_SOURCE_ABSENT = "SOURCE_ABSENT"

_ALLOWED_GATE_STATUSES = frozenset(
    {
        MEMO_PASS,
        MEMO_WATCH,
        MEMO_CLEAN_REJECT,
        MEMO_NO_VIABLE_EXPRESSION,
        MEMO_SOURCE_ABSENT,
    }
)


class CandidateMemo(BaseModel):
    """Shared specialist output; coordinator compares typed fields only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    agent_name: str
    symbol: str
    source_profile: str
    regime_label: str | None
    structure_bias: str | None
    selected_structure: str | None
    legs: list[dict[str, Any]]
    rr_actual: float | None
    pmp: float | None
    ev: float | None
    max_profit: float | None
    max_loss: float | None
    gate_status: str
    reason_code: str | None
    confidence: float | None
    source_artifacts: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("gate_status")
    @classmethod
    def _validate_gate_status(cls, value: str) -> str:
        if value not in _ALLOWED_GATE_STATUSES:
            raise ValueError(f"invalid_memo_gate_status:{value}")
        return value


class SqueezeCandidateMemo(CandidateMemo):
    """Squeeze profile specialist memo."""


class VRPCandidateMemo(CandidateMemo):
    """VRP profile specialist memo."""


class ReverseVRPCandidateMemo(CandidateMemo):
    """Reverse-VRP profile specialist memo."""


class RiskAuditMemo(CandidateMemo):
    """Risk audit layer memo (advisory only)."""
