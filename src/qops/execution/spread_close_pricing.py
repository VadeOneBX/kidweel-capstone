"""Quote-based spread close mid from Alpaca option latest quotes (CLOSE-C1B)."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Callable, Literal, Protocol

from qops.execution.alpaca_paper_bridge import load_local_env
from qops.execution.paper_payload_candidate import PaperPayloadCandidate
from qops.schemas.playbook import AllowedPlaybook

ClosePriceSource = Literal["quote_mid", "explicit"]
ClosePriceStatus = Literal["AVAILABLE", "MISSING_QUOTES", "EXPLICIT"]

_CREDIT_STRUCTURES = frozenset(
    {
        AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value,
        AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD.value,
    }
)


@dataclass(frozen=True, slots=True)
class OptionLegQuote:
    symbol: str
    bid: float | None
    ask: float | None
    mid: float | None


@dataclass(frozen=True, slots=True)
class SpreadClosePricingResult:
    quote_fetch_attempted: bool
    long_leg: OptionLegQuote | None
    short_leg: OptionLegQuote | None
    spread_mid: float | None
    suggested_close_limit: float | None
    close_price_source: ClosePriceSource
    close_price_status: ClosePriceStatus
    failure_reasons: str


class OptionQuotesFetchFn(Protocol):
    def __call__(self, symbols: tuple[str, ...]) -> dict[str, OptionLegQuote]: ...


def _env_nonempty(name: str) -> str | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    value = str(raw).strip()
    return value if value else None


def resolve_market_data_api_keys() -> tuple[str, str] | None:
    """Market-data triplet for read-only quotes (not paper transport keys)."""
    load_local_env()
    pairs = (
        ("ALPACA_API_KEY", "ALPACA_SECRET_KEY"),
        ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY"),
    )
    for key_name, secret_name in pairs:
        key = _env_nonempty(key_name)
        secret = _env_nonempty(secret_name)
        if key and secret:
            return key, secret
    return None


def _float_or_none(raw: object) -> float | None:
    if raw is None:
        return None
    try:
        out = float(raw)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def leg_mid_from_bid_ask(bid: float | None, ask: float | None) -> float | None:
    if bid is None or ask is None:
        return None
    if ask < bid:
        return None
    return (bid + ask) / 2.0


def round_option_limit_price(price: float) -> float:
    """Nearest $0.01 (no separate tick helper in repo)."""
    return round(price, 2)


def calculate_spread_close_mid(
    structure_type: str,
    *,
    long_leg_mid: float,
    short_leg_mid: float,
) -> float:
    if structure_type in _CREDIT_STRUCTURES:
        return short_leg_mid - long_leg_mid
    return long_leg_mid - short_leg_mid


def _parse_option_quote(symbol: str, raw: object) -> OptionLegQuote:
    if raw is None:
        return OptionLegQuote(symbol=symbol, bid=None, ask=None, mid=None)
    if isinstance(raw, dict):
        bid = _float_or_none(raw.get("bp") or raw.get("bid_price"))
        ask = _float_or_none(raw.get("ap") or raw.get("ask_price"))
    else:
        bid = _float_or_none(getattr(raw, "bid_price", None))
        ask = _float_or_none(getattr(raw, "ask_price", None))
    mid = leg_mid_from_bid_ask(bid, ask)
    return OptionLegQuote(symbol=symbol, bid=bid, ask=ask, mid=mid)


def fetch_alpaca_option_latest_quotes(symbols: tuple[str, ...]) -> dict[str, OptionLegQuote]:
    """Fetch latest option quotes via Alpaca market data (read-only)."""
    keys = resolve_market_data_api_keys()
    if keys is None:
        return {
            sym: OptionLegQuote(symbol=sym, bid=None, ask=None, mid=None) for sym in symbols
        }
    api_key, secret_key = keys
    from alpaca.data.historical.option import OptionHistoricalDataClient
    from alpaca.data.requests import OptionLatestQuoteRequest

    client = OptionHistoricalDataClient(
        api_key=api_key,
        secret_key=secret_key,
        raw_data=True,
    )
    request = OptionLatestQuoteRequest(symbol_or_symbols=list(symbols))
    raw = client.get_option_latest_quote(request)
    out: dict[str, OptionLegQuote] = {}
    for sym in symbols:
        quote_raw = raw.get(sym) if isinstance(raw, dict) else None
        out[sym] = _parse_option_quote(sym, quote_raw)
    return out


def price_spread_close(
    payload: PaperPayloadCandidate,
    *,
    price_source: ClosePriceSource = "quote_mid",
    explicit_limit_price: float | None = None,
    quote_fetch_fn: OptionQuotesFetchFn | None = None,
) -> SpreadClosePricingResult:
    """
    Resolve close limit from explicit override or live leg quote mids.

    Entry fill price is never used for submit pricing.
    """
    if explicit_limit_price is not None and explicit_limit_price > 0:
        limit = round_option_limit_price(explicit_limit_price)
        return SpreadClosePricingResult(
            quote_fetch_attempted=False,
            long_leg=None,
            short_leg=None,
            spread_mid=None,
            suggested_close_limit=limit,
            close_price_source="explicit",
            close_price_status="EXPLICIT",
            failure_reasons="",
        )

    if price_source != "quote_mid":
        return SpreadClosePricingResult(
            quote_fetch_attempted=False,
            long_leg=None,
            short_leg=None,
            spread_mid=None,
            suggested_close_limit=None,
            close_price_source="quote_mid",
            close_price_status="MISSING_QUOTES",
            failure_reasons="unsupported_price_source",
        )

    long_sym = payload.long_leg_symbol
    short_sym = payload.short_leg_symbol
    if not long_sym or not short_sym:
        return SpreadClosePricingResult(
            quote_fetch_attempted=False,
            long_leg=None,
            short_leg=None,
            spread_mid=None,
            suggested_close_limit=None,
            close_price_source="quote_mid",
            close_price_status="MISSING_QUOTES",
            failure_reasons="missing_leg_symbols",
        )

    if quote_fetch_fn is None and resolve_market_data_api_keys() is None:
        return SpreadClosePricingResult(
            quote_fetch_attempted=False,
            long_leg=None,
            short_leg=None,
            spread_mid=None,
            suggested_close_limit=None,
            close_price_source="quote_mid",
            close_price_status="MISSING_QUOTES",
            failure_reasons="market_data_credentials_not_ready",
        )

    fetch = quote_fetch_fn or fetch_alpaca_option_latest_quotes
    quotes = fetch((long_sym, short_sym))
    long_leg = quotes.get(long_sym)
    short_leg = quotes.get(short_sym)
    if long_leg is None or short_leg is None:
        return SpreadClosePricingResult(
            quote_fetch_attempted=True,
            long_leg=long_leg,
            short_leg=short_leg,
            spread_mid=None,
            suggested_close_limit=None,
            close_price_source="quote_mid",
            close_price_status="MISSING_QUOTES",
            failure_reasons="quote_response_incomplete",
        )

    if long_leg.mid is None or short_leg.mid is None:
        return SpreadClosePricingResult(
            quote_fetch_attempted=True,
            long_leg=long_leg,
            short_leg=short_leg,
            spread_mid=None,
            suggested_close_limit=None,
            close_price_source="quote_mid",
            close_price_status="MISSING_QUOTES",
            failure_reasons="missing_bid_ask_mid",
        )

    spread_mid = calculate_spread_close_mid(
        payload.structure_type,
        long_leg_mid=long_leg.mid,
        short_leg_mid=short_leg.mid,
    )
    if spread_mid <= 0:
        return SpreadClosePricingResult(
            quote_fetch_attempted=True,
            long_leg=long_leg,
            short_leg=short_leg,
            spread_mid=spread_mid,
            suggested_close_limit=None,
            close_price_source="quote_mid",
            close_price_status="MISSING_QUOTES",
            failure_reasons="non_positive_spread_mid",
        )

    suggested = round_option_limit_price(spread_mid)
    if suggested <= 0:
        return SpreadClosePricingResult(
            quote_fetch_attempted=True,
            long_leg=long_leg,
            short_leg=short_leg,
            spread_mid=spread_mid,
            suggested_close_limit=None,
            close_price_source="quote_mid",
            close_price_status="MISSING_QUOTES",
            failure_reasons="non_positive_suggested_limit",
        )

    return SpreadClosePricingResult(
        quote_fetch_attempted=True,
        long_leg=long_leg,
        short_leg=short_leg,
        spread_mid=spread_mid,
        suggested_close_limit=suggested,
        close_price_source="quote_mid",
        close_price_status="AVAILABLE",
        failure_reasons="",
    )


def leg_quote_to_dict(leg: OptionLegQuote | None) -> dict[str, object] | None:
    if leg is None:
        return None
    return {
        "symbol": leg.symbol,
        "bid": leg.bid,
        "ask": leg.ask,
        "mid": leg.mid,
    }
