"""Signal horizon mappings for deterministic DTE alignment."""

from __future__ import annotations

from qops.signals.classifier import SignalType
from qops.signals.constants import (
    SQUEEZE_HORIZON_MAX_DAYS,
    SQUEEZE_HORIZON_MIN_DAYS,
    WALL_REVERSAL_HORIZON_MAX_DAYS,
    WALL_REVERSAL_HORIZON_MIN_DAYS,
)


def signal_horizon_days(signal_type: SignalType) -> tuple[int, int]:
    """Return the inclusive horizon window for the signal type."""
    if signal_type == SignalType.SQUEEZE:
        return (SQUEEZE_HORIZON_MIN_DAYS, SQUEEZE_HORIZON_MAX_DAYS)
    if signal_type == SignalType.WALL_REVERSAL:
        return (WALL_REVERSAL_HORIZON_MIN_DAYS, WALL_REVERSAL_HORIZON_MAX_DAYS)
    return (0, 999)
