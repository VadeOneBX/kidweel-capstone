"""Canonical paper-live parameter references (NOTEBOOK-ALIGN-C1).

Values document alignment with `examples/options-bull-call-spread.ipynb` vs repo
defaults. This module does not fetch data, submit orders, or override gates.
"""

from __future__ import annotations

from dataclasses import dataclass

NOTEBOOK_SOURCE = "examples/options-bull-call-spread.ipynb"


@dataclass(frozen=True, slots=True)
class BullCallNotebookReference:
    """Alpaca article notebook trade-parameter block (reference only)."""

    strike_range_pct: float = 0.06
    buy_power_limit_pct: float = 0.05
    risk_free_rate: float = 0.01
    oi_threshold: int = 50
    dte_min: int = 21
    dte_max: int = 60
    target_profit_percentage: float = 0.40
    delta_stop_loss: float = 0.80
    vega_stop_loss: float = 0.40
    iv_range: tuple[float, float] = (0.20, 0.50)
    delta_range: tuple[float, float] = (0.20, 0.65)
    vega_range: tuple[float, float] = (0.01, 0.12)


@dataclass(frozen=True, slots=True)
class RepoPaperLiveDefaults:
    """Kidweel paper-live path defaults (CLI / docs; configurable, not 0DTE-locked)."""

    dte_min: int = 0
    dte_max: int = 14
    strike_buffer_pct: float = 0.03
    max_strike_distance_pct: float = 0.10
    min_dte_spread_math: int = 4
    default_bull_call_width: float = 5.0
    max_bid_ask_spread_pct: float = 0.25
    close_price_source_default: str = "quote_mid"


NOTEBOOK_BULL_CALL_REFERENCE = BullCallNotebookReference()
REPO_PAPER_LIVE_DEFAULTS = RepoPaperLiveDefaults()
