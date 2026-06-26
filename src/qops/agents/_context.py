"""Shared specialist evaluation inputs (proof harness)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class AgentEvaluateContext:
    """Bounded context for one specialist invocation."""

    candidate_id: str
    symbol: str
    source_profile: str
    regime_label: str | None = None
    structure_bias: str | None = None
    selected_structure: str | None = None
    legs: list[dict[str, Any]] = field(default_factory=list)
    rr_actual: float | None = None
    pmp: float | None = None
    ev: float | None = None
    max_profit: float | None = None
    max_loss: float | None = None
    gamma_ratio: float | None = None
    vrp: float | None = None
    tradeability_pass: bool = True
    watch_viable: bool = False
    source_artifacts: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
