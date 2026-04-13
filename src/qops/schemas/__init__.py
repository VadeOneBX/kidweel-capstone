"""Qops schema package.

Schemas are canonical handoff contracts.
Do not rename, repurpose, or silently widen schema fields once imported downstream.
Schema changes must be explicit, additive where possible, and updated across all
dependents in the same packet.
"""

from __future__ import annotations

from qops.schemas.backtest import (
    BacktestSummary,
    BacktestTradeLogRow,
    BacktestValidationResult,
    ValidationStatus,
    evaluate_backtest_gate,
)
from qops.schemas.candidate import ScreenedCandidate
from qops.schemas.environment import (
    DirectionalBias,
    EnvironmentSnapshot,
    HostageState,
    IVState,
    RegimeLabel,
    SkewState,
    WallState,
)
from qops.schemas.playbook import AllowedPlaybook, PlaybookDecision, StructureBias
from qops.schemas.risk import TradeEvaluation
from qops.schemas.structure import TradeStructureCandidate

__all__ = [
    "AllowedPlaybook",
    "BacktestSummary",
    "BacktestTradeLogRow",
    "BacktestValidationResult",
    "DirectionalBias",
    "EnvironmentSnapshot",
    "HostageState",
    "IVState",
    "PlaybookDecision",
    "RegimeLabel",
    "ScreenedCandidate",
    "SkewState",
    "StructureBias",
    "TradeEvaluation",
    "TradeStructureCandidate",
    "ValidationStatus",
    "WallState",
    "evaluate_backtest_gate",
]
