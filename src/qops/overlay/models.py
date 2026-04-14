"""Immutable Claude overlay assessment contracts (memo-only; no proposals)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OverlayAssessment:
    """Deterministic overlay memo; no execution or approval fields."""

    symbol: str

    surface_state: str
    market_state: str
    term_structure_state: str

    caution_flag: bool
    downgrade_flag: bool

    summary: str
    reason: str
