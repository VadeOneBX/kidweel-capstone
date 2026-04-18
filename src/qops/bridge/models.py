from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CandidateFlags:
    near_call_wall: bool
    near_put_wall: bool
    inverted_wall: bool
    vol_trigger_breach: bool
    cross_file_overlap: bool


@dataclass(frozen=True, slots=True)
class ChatGptCandidatePayload:
    symbol: str
    trade_date: str
    source_type: str

    price: float
    vol_trigger: float | None
    call_wall: float | None
    put_wall: float | None

    gamma_ratio: float | None
    vrp: float | None
    vrp_z: float | None
    iv_rank: float | None

    regime_label: str | None
    confidence: float | int | None
    notes: tuple[str, ...]

    flags: CandidateFlags
    market_context: dict
    chain_context: dict
