"""Environment enums and snapshot contract."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RegimeLabel(str, Enum):
    """Canonical regime label from upstream; must not be recomputed downstream."""

    BUY_PREMIUM = "BUY_PREMIUM"
    SELL_PREMIUM = "SELL_PREMIUM"
    SQUEEZE_UP = "SQUEEZE_UP"
    NEUTRAL = "NEUTRAL"


class IVState(str, Enum):
    CHEAP_VOL = "CHEAP_VOL"
    MID_VOL = "MID_VOL"
    EXPENSIVE_VOL = "EXPENSIVE_VOL"


class SkewState(str, Enum):
    PUTS_RICH = "PUTS_RICH"
    NEUTRAL = "NEUTRAL"
    CALLS_RICH = "CALLS_RICH"


class WallState(str, Enum):
    NEAR_CALL_WALL = "NEAR_CALL_WALL"
    NEAR_PUT_WALL = "NEAR_PUT_WALL"
    BETWEEN_WALLS = "BETWEEN_WALLS"
    OUTSIDE_WALLS = "OUTSIDE_WALLS"
    UNKNOWN = "UNKNOWN"


class HostageState(str, Enum):
    PINNED = "PINNED"
    PULL_TO_CALL_WALL = "PULL_TO_CALL_WALL"
    PULL_TO_PUT_WALL = "PULL_TO_PUT_WALL"
    ESCAPE_UP = "ESCAPE_UP"
    ESCAPE_DOWN = "ESCAPE_DOWN"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


class DirectionalBias(str, Enum):
    BULLISH_BIAS = "BULLISH_BIAS"
    BEARISH_BIAS = "BEARISH_BIAS"
    NEUTRAL_BIAS = "NEUTRAL_BIAS"


@dataclass(frozen=True, slots=True)
class EnvironmentSnapshot:
    """Point-in-time environment derived from a screened candidate (canonical fields preserved)."""

    symbol: str
    regime_label: RegimeLabel
    confidence: int
    gamma_ratio: float | None
    iv_state: IVState
    skew_state: SkewState
    wall_state: WallState
    directional_bias: DirectionalBias
    hostage_state: HostageState
    environment_label: str
    environment_reason: str
