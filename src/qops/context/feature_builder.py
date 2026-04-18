from __future__ import annotations

from qops.context.models import MpcChainSummary


def build_feature_row(
    *,
    candidate: dict,
    spy_context: dict,
    chain_summary: MpcChainSummary,
) -> dict:
    """Combine SpotGamma candidate fields with SPY context and delayed-chain summary features.

    Args:
        candidate: Normalized SpotGamma candidate row (dict-like).
        spy_context: Latest or as-of SPY market context row (dict-like).
        chain_summary: Output of :func:`qops.context.mcp_chain_summary.summarize_delayed_chain`.

    Returns:
        One flat dict suitable for ML / analytics frames.
    """
    return {
        "symbol": candidate["symbol"],
        "trade_date": candidate["trade_date"],
        "source_type": candidate["source_type"],
        "regime_label": candidate["regime_label"],
        "confidence": candidate["confidence"],
        "price": candidate["price"],
        "gamma_ratio": candidate.get("gamma_ratio"),
        "vrp_z": candidate.get("vrp_z"),
        "iv_rank": candidate.get("iv_rank"),
        "spy_gamma_regime": spy_context.get("gamma_regime"),
        "spy_above_vol_trigger": int(bool(spy_context.get("above_vol_trigger", False))),
        "chain_dominant_side": chain_summary.dominant_side,
        "chain_movement_bias": chain_summary.movement_bias,
        "chain_highest_oi_strike": chain_summary.highest_oi_strike,
        "chain_concentration_near_spot": chain_summary.concentration_near_spot,
    }
