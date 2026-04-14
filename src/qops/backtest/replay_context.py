"""Typed replay input for one backtest trade instance (no market simulation)."""

from __future__ import annotations

import math
from dataclasses import dataclass

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from qops.overlay.models import OverlayAssessment
from qops.schemas.risk import TradeEvaluation
from qops.schemas.structure import TradeStructureCandidate

_ALLOWED_EXIT_REASONS: frozenset[str] = frozenset(
    {
        "TP_80",
        "STOP",
        "TIME_EXIT",
        "EXPIRATION_MAX",
        "EXPIRATION_LOSS",
        "SKIP",
    }
)


@dataclass(frozen=True, slots=True)
class ReplayContext:
    """Minimum deterministic inputs to record one completed trade in a backtest."""

    symbol: str
    playbook: str

    structure: TradeStructureCandidate
    evaluation: TradeEvaluation

    entry_date: str
    exit_date: str
    dte_at_entry: int

    realized_pnl: float
    exit_reason: str

    environment_label: str
    candidate_alternatives: list[str] | None = None

    overlay: OverlayAssessment | None = None


def validate_replay_context(ctx: ReplayContext) -> None:
    """Raise clear errors if replay context is incomplete or inconsistent."""
    if not isinstance(ctx, ReplayContext):
        raise TypeError("ctx must be ReplayContext")
    if not ctx.symbol.strip():
        raise ValueError("symbol must be non-empty")
    if not ctx.playbook.strip():
        raise ValueError("playbook must be non-empty")
    if not ctx.entry_date.strip() or not ctx.exit_date.strip():
        raise ValueError("entry_date and exit_date must be non-empty")
    if ctx.exit_reason.strip() == "":
        raise ValueError("exit_reason must be non-empty")
    if ctx.exit_reason not in _ALLOWED_EXIT_REASONS:
        raise ValueError(f"exit_reason must be one of {sorted(_ALLOWED_EXIT_REASONS)}")
    if not ctx.environment_label.strip():
        raise ValueError("environment_label must be non-empty")
    if ctx.dte_at_entry < 0:
        raise ValueError("dte_at_entry must be >= 0")
    if not math.isfinite(ctx.realized_pnl):
        raise ValueError("realized_pnl must be finite")

    if not (0.0 < ctx.evaluation.pmp < 1.0) or not math.isfinite(ctx.evaluation.pmp):
        raise ValueError("evaluation.pmp must satisfy 0 < pmp < 1")
    if not math.isfinite(ctx.structure.rr_actual) or ctx.structure.rr_actual <= 0.0:
        raise ValueError("structure.rr_actual must be finite and > 0")

    if ctx.symbol != ctx.structure.symbol:
        raise ValueError("ctx.symbol must match structure.symbol")
    if ctx.symbol != ctx.evaluation.symbol:
        raise ValueError("ctx.symbol must match evaluation.symbol")
    if ctx.playbook != ctx.structure.allowed_playbook.value:
        raise ValueError("ctx.playbook must match structure.allowed_playbook")
    if ctx.playbook != ctx.evaluation.playbook:
        raise ValueError("ctx.playbook must match evaluation.playbook")

    if ctx.overlay is not None and not isinstance(ctx.overlay, OverlayAssessment):
        raise TypeError("overlay must be OverlayAssessment or None")
