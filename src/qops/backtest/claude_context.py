"""Research-only Claude candidate context for backtest replay (not a production schema)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ClaudeCandidateContext:
    """Normalized Claude file-ingestion and re-observation context for research backtests."""

    symbol: str
    source_type: str

    file_regime_label: str
    file_confidence: int

    notes: tuple[str, ...]

    session_reliability_state: str | None = None
    context_note: str | None = None
    confidence_adjustment_note: str | None = None
    classification_note: str | None = None
