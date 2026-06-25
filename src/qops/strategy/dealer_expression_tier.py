"""Dealer-weighted tier gates for hydrated spread expressions (not SpotGamma candidates)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from qops.environment.constants import IV_CHEAP_MAX, IV_EXPENSIVE_MIN
from qops.schemas.playbook import AllowedPlaybook

REVERSE_VRP_DIRECTION_SOURCE = "reverse_vrp_iv_rv_wall_skew"
GAMMA_RATIO_DIRECTION_SOURCE = "gamma_ratio"

DIRECTION_STATUS_SOURCE_POPULATED = "SOURCE_POPULATED"
DIRECTION_STATUS_SOURCE_DERIVED = "SOURCE_DERIVED"
DIRECTION_STATUS_SOURCE_MISSING = "SOURCE_MISSING"
DIRECTION_STATUS_NOT_APPLICABLE = "NOT_APPLICABLE"

TIER_TABLE: tuple[tuple[str, int, int, float, float], ...] = (
    ("A", 10, 12, 1.05, 0.55),
    ("B", 8, 9, 1.15, 0.52),
    ("C", 6, 7, 1.25, 0.48),
    ("D", 4, 5, 1.40, 0.45),
    ("E", 0, 3, 1.50, 0.42),
)


@dataclass(frozen=True, slots=True)
class DealerTierGate:
    tier: str
    dealer_weighted_score: int
    rr_dealer_required: float
    pmp_dealer_max: float


def dealer_tier_for_score(score: int) -> DealerTierGate:
    clamped = max(0, min(12, int(score)))
    for tier, lo, hi, rr_req, pmp_max in TIER_TABLE:
        if lo <= clamped <= hi:
            return DealerTierGate(
                tier=tier,
                dealer_weighted_score=clamped,
                rr_dealer_required=rr_req,
                pmp_dealer_max=pmp_max,
            )
    return DealerTierGate(
        tier="E",
        dealer_weighted_score=clamped,
        rr_dealer_required=1.50,
        pmp_dealer_max=0.42,
    )


def _component_score_0_3(value: float, *, thresholds: tuple[tuple[float, int], ...]) -> int:
    for bound, score in thresholds:
        if value <= bound:
            return score
    return 0


def wall_proximity_score(short_strike_wall_distance_pct: float | None) -> int:
    if short_strike_wall_distance_pct is None or not math.isfinite(short_strike_wall_distance_pct):
        return 0
    distance = abs(short_strike_wall_distance_pct)
    return _component_score_0_3(
        distance,
        thresholds=((0.02, 3), (0.05, 2), (0.10, 1), (math.inf, 0)),
    )


def cheap_iv_score(iv_rank: float | None) -> int:
    if iv_rank is None or not math.isfinite(iv_rank):
        return 0
    if iv_rank <= IV_CHEAP_MAX:
        return 3
    if iv_rank <= 50.0:
        return 2
    if iv_rank <= IV_EXPENSIVE_MIN:
        return 1
    return 0


@dataclass(frozen=True, slots=True)
class DealerDirectionResolution:
    score: int
    source: str
    status: str
    reason: str


@dataclass(frozen=True, slots=True)
class ReverseVrpDirectionRow:
    current_price: float | None
    call_wall: float | None
    put_wall: float | None
    hedge_wall: float | None
    skew: float | None
    ne_skew: float | None
    one_month_iv: float | None
    one_month_rv: float | None
    iv_rank: float | None
    vrp: float | None


def dealer_direction_score_from_gamma(gamma_ratio: float | None) -> int:
    if gamma_ratio is None or not math.isfinite(gamma_ratio):
        return 0
    if gamma_ratio >= 1.5:
        return 3
    if gamma_ratio >= 1.2:
        return 2
    if gamma_ratio >= 1.0:
        return 1
    return 0


def dealer_direction_score(gamma_ratio: float | None) -> int:
    return dealer_direction_score_from_gamma(gamma_ratio)


def _finite_float(raw: object) -> float | None:
    if raw is None:
        return None
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    return val if math.isfinite(val) else None


def reverse_vrp_direction_row_from_mapping(row: dict[str, object]) -> ReverseVrpDirectionRow:
    iv = _finite_float(row.get("one_month_iv"))
    rv = _finite_float(row.get("one_month_rv"))
    vrp = _finite_float(row.get("vrp"))
    if vrp is None and iv is not None and rv is not None:
        vrp = iv - rv
    return ReverseVrpDirectionRow(
        current_price=_finite_float(row.get("current_price")),
        call_wall=_finite_float(row.get("call_wall")),
        put_wall=_finite_float(row.get("put_wall")),
        hedge_wall=_finite_float(row.get("hedge_wall")),
        skew=_finite_float(row.get("skew")),
        ne_skew=_finite_float(row.get("ne_skew")),
        one_month_iv=iv,
        one_month_rv=rv,
        iv_rank=_finite_float(row.get("iv_rank")),
        vrp=vrp,
    )


def reverse_vrp_direction_score(
    row: ReverseVrpDirectionRow,
    *,
    structure: str,
    short_strike: float | None,
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []

    if row.vrp is not None and row.vrp < 0:
        score += 1
        reasons.append("cheap_iv_vrp_negative")

    if structure == AllowedPlaybook.BULL_CALL_SPREAD.value:
        if (
            row.call_wall is not None
            and row.current_price is not None
            and row.call_wall > row.current_price
        ):
            score += 1
            reasons.append("call_wall_above_spot")
        if (
            short_strike is not None
            and row.call_wall is not None
            and row.call_wall > 0
            and abs(short_strike - row.call_wall) / row.call_wall <= 0.05
        ):
            score += 1
            reasons.append("short_call_wall_aligned")
        if row.skew is not None and row.skew > -0.10:
            score += 1
            reasons.append("skew_not_strongly_bearish")

    if structure == AllowedPlaybook.BEAR_PUT_SPREAD.value:
        if (
            row.put_wall is not None
            and row.current_price is not None
            and row.put_wall <= row.current_price
        ):
            score += 1
            reasons.append("put_wall_below_or_near_spot")
        if (
            short_strike is not None
            and row.put_wall is not None
            and row.put_wall > 0
            and abs(short_strike - row.put_wall) / row.put_wall <= 0.05
        ):
            score += 1
            reasons.append("short_put_wall_aligned")
        if row.skew is not None and row.skew < 0.10:
            score += 1
            reasons.append("skew_not_strongly_bullish")

    return min(score, 3), reasons


def _reverse_vrp_required_fields_present(row: ReverseVrpDirectionRow) -> bool:
    if row.current_price is None or row.current_price <= 0:
        return False
    if row.call_wall is None and row.put_wall is None:
        return False
    return True


def resolve_dealer_direction_score(
    *,
    source_profile: str | None,
    gamma_ratio: float | None,
    candidate_row: dict[str, object],
    structure: str,
    short_strike: float | None,
) -> DealerDirectionResolution:
    profile = (source_profile or str(candidate_row.get("source_profile", ""))).strip().lower()
    if profile == "reverse_vrp":
        rv_row = reverse_vrp_direction_row_from_mapping(candidate_row)
        if not _reverse_vrp_required_fields_present(rv_row):
            return DealerDirectionResolution(
                score=0,
                source=REVERSE_VRP_DIRECTION_SOURCE,
                status=DIRECTION_STATUS_SOURCE_MISSING,
                reason="missing_reverse_vrp_direction_fields",
            )
        score, reason_tags = reverse_vrp_direction_score(
            rv_row,
            structure=structure,
            short_strike=short_strike,
        )
        return DealerDirectionResolution(
            score=score,
            source=REVERSE_VRP_DIRECTION_SOURCE,
            status=DIRECTION_STATUS_SOURCE_DERIVED,
            reason=",".join(reason_tags) if reason_tags else "reverse_vrp_direction_derived",
        )

    if gamma_ratio is not None and math.isfinite(gamma_ratio):
        return DealerDirectionResolution(
            score=dealer_direction_score_from_gamma(gamma_ratio),
            source=GAMMA_RATIO_DIRECTION_SOURCE,
            status=DIRECTION_STATUS_SOURCE_POPULATED,
            reason="gamma_ratio_sourced",
        )
    return DealerDirectionResolution(
        score=0,
        source=GAMMA_RATIO_DIRECTION_SOURCE,
        status=DIRECTION_STATUS_SOURCE_MISSING,
        reason="gamma_ratio_absent",
    )


def spread_efficiency_score(*, net_debit: float, spread_width: float) -> int:
    if spread_width <= 0 or net_debit <= 0:
        return 0
    if not math.isfinite(net_debit) or not math.isfinite(spread_width):
        return 0
    ratio = net_debit / spread_width
    return _component_score_0_3(
        ratio,
        thresholds=((0.25, 3), (0.40, 2), (0.55, 1), (math.inf, 0)),
    )


def compute_dealer_weighted_score(
    *,
    short_strike_wall_distance_pct: float | None,
    iv_rank: float | None,
    gamma_ratio: float | None,
    net_debit: float,
    spread_width: float,
    resolved_direction_score: int | None = None,
) -> tuple[int, int, int, int, int]:
    wall = wall_proximity_score(short_strike_wall_distance_pct)
    cheap = cheap_iv_score(iv_rank)
    if resolved_direction_score is not None:
        direction = max(0, min(3, int(resolved_direction_score)))
    else:
        direction = dealer_direction_score_from_gamma(gamma_ratio)
    efficiency = spread_efficiency_score(net_debit=net_debit, spread_width=spread_width)
    total = wall + cheap + direction + efficiency
    return total, wall, cheap, direction, efficiency


def expression_passes_dealer_tier(
    *,
    reward_risk: float | None,
    pmp: float | None,
    gate: DealerTierGate,
) -> bool:
    if reward_risk is None or pmp is None:
        return False
    if not math.isfinite(reward_risk) or not math.isfinite(pmp):
        return False
    if reward_risk < gate.rr_dealer_required:
        return False
    return pmp <= gate.pmp_dealer_max


def structure_direction(structure_type: str) -> str:
    if structure_type == AllowedPlaybook.BULL_CALL_SPREAD.value:
        return "BULLISH"
    if structure_type == AllowedPlaybook.BEAR_PUT_SPREAD.value:
        return "BEARISH"
    return "NEUTRAL"
