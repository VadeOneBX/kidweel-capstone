from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class SpyMarketContext:
    trade_date: date
    close: float
    vol_trigger: float | None
    call_wall: float | None
    put_wall: float | None
    gamma_regime: str
    above_vol_trigger: bool
    note: str = ""


@dataclass(frozen=True, slots=True)
class MpcChainSummary:
    symbol: str
    nearest_expiration: str
    highest_oi_strike: float | None
    total_call_oi: int
    total_put_oi: int
    dominant_side: str
    concentration_near_spot: float | None
    movement_bias: str
    note: str = ""
