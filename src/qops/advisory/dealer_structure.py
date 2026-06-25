"""Day-over-day dealer structure recognition from SpotGamma SPY context (pre-AM note)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from qops.advisory.am_note_gate import _spy_snapshots_from_context

GammaRegimeState = Literal[
    "POSITIVE_GAMMA_STABLE",
    "NEGATIVE_GAMMA_UNSTABLE",
    "TRANSITIONAL_GAMMA",
    "UNKNOWN_GAMMA_STATE",
]

WallMovement = Literal[
    "PUT_WALL_MOVED_UP",
    "PUT_WALL_MOVED_DOWN",
    "PUT_WALL_UNCHANGED",
    "CALL_WALL_MOVED_UP",
    "CALL_WALL_MOVED_DOWN",
    "CALL_WALL_UNCHANGED",
]

PreAmAdvisoryBias = Literal[
    "DEFENSIVE",
    "SELECTIVE_LONG_DELTA",
    "WAIT_FOR_CONFIRMATION",
    "RISK_ON",
    "NO_EDGE",
]


@dataclass(frozen=True, slots=True)
class DealerStructureSnapshot:
    trade_date: str
    spot: float | None
    call_wall: float | None
    put_wall: float | None
    vol_trigger: float | None
    gamma_ratio: float | None
    one_month_iv: float | None
    one_month_rv: float | None
    iv_rank: float | None
    low_vol_point: float | None
    high_vol_point: float | None


@dataclass(frozen=True, slots=True)
class DealerStructureAssessment:
    gamma_regime: GammaRegimeState
    put_wall_movement: WallMovement
    call_wall_movement: WallMovement
    advisory_bias: PreAmAdvisoryBias
    structure_summary: str
    current: DealerStructureSnapshot | None
    prior: DealerStructureSnapshot | None


def _snap_from_row(row: dict[str, object]) -> DealerStructureSnapshot:
    hedge = row.get("hedge_wall")
    return DealerStructureSnapshot(
        trade_date=str(row.get("trade_date", "")),
        spot=None if row.get("spot") is None else float(row["spot"]),  # type: ignore[arg-type]
        call_wall=None if row.get("call_wall") is None else float(row["call_wall"]),  # type: ignore[arg-type]
        put_wall=None if row.get("put_wall") is None else float(row["put_wall"]),  # type: ignore[arg-type]
        vol_trigger=None if hedge is None else float(hedge),  # type: ignore[arg-type]
        gamma_ratio=None if row.get("gamma_ratio") is None else float(row["gamma_ratio"]),  # type: ignore[arg-type]
        one_month_iv=None if row.get("one_month_iv") is None else float(row["one_month_iv"]),  # type: ignore[arg-type]
        one_month_rv=None if row.get("one_month_rv") is None else float(row["one_month_rv"]),  # type: ignore[arg-type]
        iv_rank=None if row.get("iv_rank") is None else float(row["iv_rank"]),  # type: ignore[arg-type]
        low_vol_point=None,
        high_vol_point=None,
    )


def _wall_movement(
    current: float | None,
    prior: float | None,
    *,
    prefix: Literal["PUT_WALL", "CALL_WALL"],
) -> WallMovement:
    if current is None or prior is None:
        unchanged = f"{prefix}_UNCHANGED"
        return unchanged  # type: ignore[return-value]
    if current > prior:
        return f"{prefix}_MOVED_UP"  # type: ignore[return-value]
    if current < prior:
        return f"{prefix}_MOVED_DOWN"  # type: ignore[return-value]
    return f"{prefix}_UNCHANGED"  # type: ignore[return-value]


def _gamma_regime(current: DealerStructureSnapshot) -> GammaRegimeState:
    if current.gamma_ratio is None:
        return "UNKNOWN_GAMMA_STATE"
    if current.gamma_ratio < 1.0:
        return "NEGATIVE_GAMMA_UNSTABLE"
    if (
        current.vol_trigger is not None
        and current.spot is not None
        and current.spot < current.vol_trigger
    ):
        return "TRANSITIONAL_GAMMA"
    return "POSITIVE_GAMMA_STABLE"


def _advisory_bias(
    gamma: GammaRegimeState,
    put_move: WallMovement,
    call_move: WallMovement,
) -> PreAmAdvisoryBias:
    if gamma == "NEGATIVE_GAMMA_UNSTABLE":
        return "DEFENSIVE"
    if gamma == "TRANSITIONAL_GAMMA":
        return "WAIT_FOR_CONFIRMATION"
    if put_move == "PUT_WALL_MOVED_DOWN" or call_move == "CALL_WALL_MOVED_DOWN":
        return "DEFENSIVE"
    if gamma == "POSITIVE_GAMMA_STABLE":
        return "SELECTIVE_LONG_DELTA"
    return "NO_EDGE"


def assess_dealer_structure(context_df: pd.DataFrame) -> DealerStructureAssessment:
    raw = _spy_snapshots_from_context(context_df)
    if not raw:
        return DealerStructureAssessment(
            gamma_regime="UNKNOWN_GAMMA_STATE",
            put_wall_movement="PUT_WALL_UNCHANGED",
            call_wall_movement="CALL_WALL_UNCHANGED",
            advisory_bias="WAIT_FOR_CONFIRMATION",
            structure_summary=(
                "Pre-AM note dealer structure unavailable; wait for Founder note before paper approval."
            ),
            current=None,
            prior=None,
        )

    current = _snap_from_row(raw[-1])
    prior = _snap_from_row(raw[-2]) if len(raw) >= 2 else None
    gamma = _gamma_regime(current)
    put_move = _wall_movement(
        current.put_wall,
        prior.put_wall if prior else None,
        prefix="PUT_WALL",
    )
    call_move = _wall_movement(
        current.call_wall,
        prior.call_wall if prior else None,
        prefix="CALL_WALL",
    )
    bias = _advisory_bias(gamma, put_move, call_move)

    if bias == "DEFENSIVE":
        summary = (
            "Pre-AM note structure is defensive. Gamma regime appears unstable, and the advisory "
            "should wait for the Founder's Note before promoting directional bull call spreads. "
            "Candidates may be hydrated, but approvals should remain withheld."
        )
    else:
        summary = (
            "Pre-AM note structure recorded from SpotGamma; AM Founder note still required "
            "before paper approval."
        )

    return DealerStructureAssessment(
        gamma_regime=gamma,
        put_wall_movement=put_move,
        call_wall_movement=call_move,
        advisory_bias=bias,
        structure_summary=summary,
        current=current,
        prior=prior,
    )
