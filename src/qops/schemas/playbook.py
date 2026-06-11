"""Playbook enums and decision record."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StructureBias(str, Enum):
    """Canonical upstream structure intent; downstream must not replace it."""

    BULL_CALL_SPREAD = "BULL_CALL_SPREAD"
    BEAR_PUT_SPREAD = "BEAR_PUT_SPREAD"
    BULL_PUT_CREDIT_SPREAD = "BULL_PUT_CREDIT_SPREAD"
    BEAR_CALL_CREDIT_SPREAD = "BEAR_CALL_CREDIT_SPREAD"
    LONG_CALL_PARKED = "LONG_CALL_PARKED"
    LONG_GAMMA_HEDGE = "LONG_GAMMA_HEDGE"
    SKIP = "SKIP"


class AllowedPlaybook(str, Enum):
    """Confirmed or downgraded playbook; may match structure_bias or downgrade to SKIP only."""

    BULL_CALL_SPREAD = "BULL_CALL_SPREAD"
    BEAR_PUT_SPREAD = "BEAR_PUT_SPREAD"
    BULL_PUT_CREDIT_SPREAD = "BULL_PUT_CREDIT_SPREAD"
    BEAR_CALL_CREDIT_SPREAD = "BEAR_CALL_CREDIT_SPREAD"
    LONG_CALL_PARKED = "LONG_CALL_PARKED"
    LONG_GAMMA_HEDGE = "LONG_GAMMA_HEDGE"
    SKIP = "SKIP"


@dataclass(frozen=True, slots=True)
class PlaybookDecision:
    """Result of confirming upstream structure_bias or downgrading to SKIP."""

    symbol: str
    structure_bias: StructureBias
    allowed_playbook: AllowedPlaybook
    conflict_flag: bool
    skip_flag: bool
    decision_reason: str
