"""Canonical SpotGamma row model for weekly candidate surface exports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

SourceType = Literal["SQUEEZE", "VRP", "REVERSE_VRP"]


@dataclass(frozen=True, slots=True)
class SpotGammaRecord:
    """One normalized row from a SpotGamma XLSX export."""

    trade_date: date
    symbol: str
    source_type: SourceType
    price: float | None
    vol_trigger: float | None
    call_wall: float | None
    put_wall: float | None
    gamma_ratio: float | None
    vrp: float | None
    vrp_z: float | None
    iv_rank: float | None
    regime_label: str | None
    confidence: float
    notes: tuple[str, ...]
