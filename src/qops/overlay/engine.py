"""Deterministic overlay memo builder from prepared context (no API calls)."""

from __future__ import annotations

from qops.overlay.models import OverlayAssessment


def _map_surface(skew_state: str) -> str:
    if skew_state == "CALLS_RICH":
        return "UPSIDE_RICH"
    if skew_state == "PUTS_RICH":
        return "DOWNSIDE_RICH"
    if skew_state == "NEUTRAL":
        return "BALANCED_SURFACE"
    return "UNKNOWN"


def _map_market(iv_state: str) -> str:
    if iv_state == "EXPENSIVE_VOL":
        return "BROAD_DEFENSIVE_PRICING"
    if iv_state == "CHEAP_VOL":
        return "COMPRESSED_VOL_REGIME"
    if iv_state == "MID_VOL":
        return "NORMALIZING_PRICING"
    return "UNKNOWN"


def _map_term(wall_state: str) -> str:
    if wall_state in ("NEAR_CALL_WALL", "NEAR_PUT_WALL"):
        return "FRONT_VOL_ELEVATED"
    if wall_state == "BETWEEN_WALLS":
        return "TERM_STRUCTURE_FLAT"
    if wall_state == "OUTSIDE_WALLS":
        return "EVENT_DISTORTED_SURFACE"
    return "UNKNOWN"


def _build_summary(
    surface_state: str,
    market_state: str,
    term_structure_state: str,
    caution_flag: bool,
    downgrade_flag: bool,
) -> str:
    parts: list[str] = []
    if surface_state == "UPSIDE_RICH":
        parts.append("Upside wing appears rich")
    elif surface_state == "DOWNSIDE_RICH":
        parts.append("Downside wing appears rich")
    elif surface_state == "BALANCED_SURFACE":
        parts.append("Skew surface is balanced")
    else:
        parts.append("Surface state indeterminate")

    if market_state == "BROAD_DEFENSIVE_PRICING":
        parts.append("volatility is broadly defensive vs history")
    elif market_state == "COMPRESSED_VOL_REGIME":
        parts.append("volatility is compressed vs history")
    elif market_state == "NORMALIZING_PRICING":
        parts.append("volatility is mid-range")
    else:
        parts.append("market vol regime unclear")

    if term_structure_state == "FRONT_VOL_ELEVATED":
        parts.append("front-term vol elevated vs walls")
    elif term_structure_state == "TERM_STRUCTURE_FLAT":
        parts.append("term structure between walls")
    elif term_structure_state == "EVENT_DISTORTED_SURFACE":
        parts.append("walls outside — event-style distortion risk")
    else:
        parts.append("term structure unclear")

    if caution_flag:
        parts.append("caution on directional debit spend")
    if downgrade_flag:
        parts.append("downgrade posture recommended")

    return "; ".join(parts) + "."


def build_overlay_assessment(
    *,
    symbol: str,
    iv_state: str,
    skew_state: str,
    wall_state: str,
) -> OverlayAssessment:
    """
    Build a deterministic overlay assessment from prepared context.

    Maps environment strings to memo-only surface / market / term labels and
    conservative caution/downgrade flags. Does not call external services.
    """
    if not symbol.strip():
        raise ValueError("symbol must be non-empty")

    surface_state = _map_surface(skew_state)
    market_state = _map_market(iv_state)
    term_structure_state = _map_term(wall_state)

    caution_flag = surface_state in ("UPSIDE_RICH", "DOWNSIDE_RICH") or market_state == (
        "BROAD_DEFENSIVE_PRICING"
    )
    downgrade_flag = market_state == "BROAD_DEFENSIVE_PRICING" and wall_state == "OUTSIDE_WALLS"

    reason = (
        f"{skew_state} mapped to {surface_state}; "
        f"{iv_state} mapped to {market_state}; "
        f"{wall_state} mapped to {term_structure_state}."
    )

    summary = _build_summary(
        surface_state,
        market_state,
        term_structure_state,
        caution_flag,
        downgrade_flag,
    )

    return OverlayAssessment(
        symbol=symbol.strip(),
        surface_state=surface_state,
        market_state=market_state,
        term_structure_state=term_structure_state,
        caution_flag=caution_flag,
        downgrade_flag=downgrade_flag,
        summary=summary,
        reason=reason,
    )
