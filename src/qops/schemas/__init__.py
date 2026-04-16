"""Qops schema package.

Schemas are canonical handoff contracts.
Do not rename, repurpose, or silently widen schema fields once imported downstream.
Schema changes must be explicit, additive where possible, and updated across all
dependents in the same packet.
"""

from __future__ import annotations

from importlib import import_module

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

_EXPORT_MODULES: dict[str, str] = {
    "AllowedPlaybook": "qops.schemas.playbook",
    "BacktestSummary": "qops.schemas.backtest",
    "BacktestTradeLogRow": "qops.schemas.backtest",
    "BacktestValidationResult": "qops.schemas.backtest",
    "DirectionalBias": "qops.schemas.environment",
    "EnvironmentSnapshot": "qops.schemas.environment",
    "HostageState": "qops.schemas.environment",
    "IVState": "qops.schemas.environment",
    "PlaybookDecision": "qops.schemas.playbook",
    "RegimeLabel": "qops.schemas.environment",
    "ScreenedCandidate": "qops.schemas.candidate",
    "SkewState": "qops.schemas.environment",
    "StructureBias": "qops.schemas.playbook",
    "TradeEvaluation": "qops.schemas.risk",
    "TradeStructureCandidate": "qops.schemas.structure",
    "ValidationStatus": "qops.schemas.backtest",
    "WallState": "qops.schemas.environment",
    "evaluate_backtest_gate": "qops.schemas.backtest",
}


def __getattr__(name: str) -> object:
    """Lazily resolve schema re-exports to avoid package import cycles."""
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value
