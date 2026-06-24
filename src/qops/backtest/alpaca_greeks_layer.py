"""Alpaca-first greeks staging for narrowed blueprint plans (no execution, no Databento)."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, fields, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from qops.backtest.alpaca_blueprint_adapter import (
    AlpacaBlueprintReplayPlanRow,
    build_blueprint_request_plan,
    expiration_window_label,
    filter_ready_for_fetch,
    load_availability_plan,
    strike_bounds,
)
from qops.backtest.alpaca_replay_inputs import ReplayCandidateRow, load_replay_candidates
from qops.backtest.spotgamma_replay_builder import assess_context_csv_freshness
from qops.bridge.chain_snapshot_export import parse_occ_us_option_contract

PROVENANCE_TAG = "alpaca_greeks_c1_staging"

GreeksSource = Literal["alpaca_snapshot", "computed_bs", "missing"]
GreeksStatus = Literal["AVAILABLE", "COMPUTED", "MISSING", "INVALID_INPUTS"]
GreeksConfidence = Literal["high", "medium", "low", "none"]


@dataclass(frozen=True, slots=True)
class AlpacaGreeksCandidateRow:
    underlying_symbol: str
    trade_date: str
    current_price: float
    option_symbol: str
    expiration: str
    strike: float
    option_type: str
    bid: float | None
    ask: float | None
    mid: float | None
    latest_trade: float | None
    delta: float | None
    gamma: float | None
    theta: float | None
    vega: float | None
    rho: float | None
    implied_volatility: float | None
    greeks_source: GreeksSource
    greeks_status: GreeksStatus
    greeks_confidence: GreeksConfidence
    volatility_is_proxy: bool
    provenance: str
    blueprint_provenance: str
    source_profile: str
    has_spy_context: bool
    mode: str = "historical_replay"
    source: str = "alpaca_greeks_c1_staging"


PAPER_LIVE_MODE = "paper_live"
HISTORICAL_REPLAY_MODE = "historical_replay"
PAPER_LIVE_ROW_SOURCE = "alpaca_paper_live_chain"
PAPER_LIVE_PROVENANCE = "alpaca_greeks_c1b_paper_live"


FetchFailureClass = Literal[
    "EMPTY_FETCH_RESULT",
    "REQUEST_INVALID",
    "CLIENT_METHOD_UNSUPPORTED",
    "PERMISSION_OR_SUBSCRIPTION_ERROR",
    "API_SHAPE_MISMATCH",
    "FILTER_REMOVED_ALL_ROWS",
]


@dataclass(frozen=True, slots=True)
class GreeksFetchDiagnostics:
    """Aggregated read-only fetch diagnostics (no secrets)."""

    fetch_attempted: bool
    blueprint_rows: int
    requests_attempted: int
    requests_empty: int
    requests_error: int
    requests_invalid: int
    contracts_before_filter: int
    contracts_removed_by_filter: int
    contracts_after_filter: int
    contracts_staged: int
    request_descriptors: tuple[dict[str, object], ...]
    empty_response_reasons: tuple[str, ...]
    error_summaries: tuple[str, ...]
    failure_class: FetchFailureClass | None
    staging_mode: str = HISTORICAL_REPLAY_MODE
    symbols_requested: tuple[str, ...] = ()
    symbol_source: str = ""
    contracts_removed_by_dte_filter: int = 0
    contracts_removed_by_strike_filter: int = 0


@dataclass(frozen=True, slots=True)
class PaperLiveSymbolSpec:
    symbol: str
    current_price: float | None
    source_profile: str
    has_spy_context: bool
    provenance: str


@dataclass(frozen=True, slots=True)
class _ChainFilterStats:
    removed_by_dte: int
    removed_by_strike: int


@dataclass(frozen=True, slots=True)
class _FetchAttemptResult:
    outcome: Literal["ok", "empty", "error", "invalid"]
    contracts_before_filter: int
    contracts_after_filter: int
    filtered_snapshots: dict[str, Any]
    empty_reason: str | None
    error_summary: str | None
    removed_by_dte: int = 0
    removed_by_strike: int = 0


def sanitize_blueprint_descriptor(plan: AlpacaBlueprintReplayPlanRow) -> dict[str, object]:
    return {
        "symbol": plan.symbol.strip().upper(),
        "trade_date": plan.trade_date.strip(),
        "expiration_window": plan.expiration_window,
        "strike_lower_bound": plan.strike_lower_bound,
        "strike_upper_bound": plan.strike_upper_bound,
        "dte_min": plan.dte_min,
        "dte_max": plan.dte_max,
        "current_price": plan.current_price,
    }


def validate_blueprint_for_chain_request(plan: AlpacaBlueprintReplayPlanRow) -> tuple[bool, str | None]:
    symbol = plan.symbol.strip()
    if not symbol:
        return False, "missing_symbol"
    if not plan.trade_date.strip():
        return False, "missing_trade_date"
    try:
        date.fromisoformat(plan.trade_date.strip())
    except ValueError:
        return False, "invalid_trade_date"
    if not math.isfinite(plan.current_price) or plan.current_price <= 0:
        return False, "invalid_current_price"
    if plan.dte_min < 0 or plan.dte_max < plan.dte_min:
        return False, "invalid_dte_window"
    try:
        exp_lo, exp_hi = _parse_expiration_window(plan.expiration_window)
    except ValueError:
        return False, "invalid_expiration_window"
    if exp_hi < exp_lo:
        return False, "invalid_expiration_window"
    if not math.isfinite(plan.strike_lower_bound) or not math.isfinite(plan.strike_upper_bound):
        return False, "invalid_strike_bounds"
    if plan.strike_upper_bound <= plan.strike_lower_bound:
        return False, "invalid_strike_bounds"
    return True, None


def _classify_fetch_exception(exc: BaseException) -> str:
    text = f"{type(exc).__name__}:{exc}".lower()
    if any(token in text for token in ("401", "403", "forbidden", "unauthorized", "subscription", "permission")):
        return "PERMISSION_OR_SUBSCRIPTION_ERROR"
    if isinstance(exc, AttributeError) or "has no attribute" in text:
        return "CLIENT_METHOD_UNSUPPORTED"
    return "API_SHAPE_MISMATCH"


def resolve_fetch_failure_class(diag: GreeksFetchDiagnostics) -> FetchFailureClass | None:
    if not diag.fetch_attempted:
        return None
    if diag.contracts_staged > 0:
        return None
    if diag.requests_invalid > 0 and diag.requests_attempted == 0:
        return "REQUEST_INVALID"
    if diag.requests_invalid == diag.blueprint_rows and diag.blueprint_rows > 0:
        return "REQUEST_INVALID"
    for err in diag.error_summaries:
        if err.startswith("PERMISSION_OR_SUBSCRIPTION_ERROR"):
            return "PERMISSION_OR_SUBSCRIPTION_ERROR"
        if err.startswith("CLIENT_METHOD_UNSUPPORTED"):
            return "CLIENT_METHOD_UNSUPPORTED"
    if diag.requests_error > 0 and diag.requests_empty + diag.requests_error >= diag.requests_attempted:
        if diag.contracts_before_filter == 0:
            return "API_SHAPE_MISMATCH"
    if diag.contracts_before_filter > 0 and diag.contracts_after_filter == 0:
        return "FILTER_REMOVED_ALL_ROWS"
    if diag.requests_empty > 0 and diag.requests_attempted > 0 and diag.contracts_before_filter == 0:
        return "EMPTY_FETCH_RESULT"
    if diag.fetch_attempted and diag.contracts_staged == 0:
        return "EMPTY_FETCH_RESULT"
    return None


def fetch_diagnostics_summary(diag: GreeksFetchDiagnostics) -> dict[str, object]:
    return {
        "mode": diag.staging_mode,
        "symbols_requested": list(diag.symbols_requested),
        "symbol_source": diag.symbol_source,
        "requests_attempted": diag.requests_attempted,
        "requests_empty": diag.requests_empty,
        "requests_error": diag.requests_error,
        "requests_invalid": diag.requests_invalid,
        "contracts_before_filter": diag.contracts_before_filter,
        "contracts_removed_by_filter": diag.contracts_removed_by_filter,
        "contracts_removed_by_dte_filter": diag.contracts_removed_by_dte_filter,
        "contracts_removed_by_strike_filter": diag.contracts_removed_by_strike_filter,
        "contracts_after_filter": diag.contracts_after_filter,
        "contracts_staged": diag.contracts_staged,
        "failure_class": diag.failure_class,
        "request_descriptors_sample": list(diag.request_descriptors),
        "empty_response_reasons_sample": list(diag.empty_response_reasons),
        "error_summaries_sample": list(diag.error_summaries),
    }


def load_blueprint_plan_from_csv(path: str | Path) -> list[AlpacaBlueprintReplayPlanRow]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"blueprint replay plan csv not found: {p.resolve()}")
    df = pd.read_csv(p)
    out: list[AlpacaBlueprintReplayPlanRow] = []
    for _, series in df.iterrows():
        kwargs: dict[str, object] = {}
        for f in fields(AlpacaBlueprintReplayPlanRow):
            name = f.name
            raw = series[name] if name in series.index else None
            if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                if name in {"dte_min", "dte_max"}:
                    kwargs[name] = 0
                elif name == "has_spy_context":
                    kwargs[name] = False
                elif name == "current_price":
                    kwargs[name] = 0.0
                else:
                    kwargs[name] = ""
                continue
            if name == "has_spy_context":
                kwargs[name] = str(raw).strip().lower() in {"1", "true", "yes"} if not isinstance(raw, bool) else raw
            elif name in {"dte_min", "dte_max"}:
                kwargs[name] = int(raw)
            elif name in {"current_price", "strike_lower_bound", "strike_upper_bound"}:
                kwargs[name] = float(raw)
            else:
                kwargs[name] = str(raw).strip()
        out.append(AlpacaBlueprintReplayPlanRow(**kwargs))  # type: ignore[arg-type]
    return out


def load_blueprint_request_plans(
    *,
    input_csv: Path,
    availability_csv: Path,
    candidates_csv: Path,
    spotgamma_root: Path,
    rebuild_if_missing: bool,
    dte_min: int,
    dte_max: int,
    strike_buffer_pct: float,
    limit: int | None,
) -> tuple[list[AlpacaBlueprintReplayPlanRow], str]:
    if input_csv.is_file():
        plans = load_blueprint_plan_from_csv(input_csv)
        if limit is not None and limit > 0:
            plans = plans[:limit]
        return plans, "blueprint_plan_csv"
    if not rebuild_if_missing:
        raise SystemExit(
            f"Blueprint plan not found: {input_csv}. Pass --rebuild-if-missing to rebuild via C4A."
        )
    availability, _ = load_availability_plan(
        input_csv=availability_csv,
        candidates_csv=candidates_csv,
        spotgamma_root=spotgamma_root,
        rebuild_if_missing=True,
        dte_min=dte_min,
        dte_max=dte_max,
    )
    ready = filter_ready_for_fetch(availability)
    plans = build_blueprint_request_plan(
        ready,
        dte_min=dte_min,
        dte_max=dte_max,
        strike_buffer_pct=strike_buffer_pct,
        limit=limit,
    )
    return plans, "rebuilt_c4a_blueprint_plan"


def _today_trade_date() -> str:
    return date.today().isoformat()


def _latest_candidate_price_by_symbol(
    candidates: list[ReplayCandidateRow],
) -> dict[str, ReplayCandidateRow]:
    best: dict[str, ReplayCandidateRow] = {}
    for row in candidates:
        sym = row.symbol.strip().upper()
        if not sym:
            continue
        prev = best.get(sym)
        if prev is None or row.trade_date > prev.trade_date:
            best[sym] = row
    return best


def _optional_replay_candidates(
    candidates_csv: Path,
    spotgamma_root: Path,
) -> list[ReplayCandidateRow]:
    if candidates_csv.is_file():
        rows, _ = load_replay_candidates(
            input_csv=candidates_csv,
            spotgamma_root=spotgamma_root,
            rebuild_if_missing=False,
        )
        return rows
    if spotgamma_root.is_dir():
        rows, _ = load_replay_candidates(
            input_csv=candidates_csv,
            spotgamma_root=spotgamma_root,
            rebuild_if_missing=True,
        )
        return rows
    return []


def resolve_paper_live_symbol_specs(
    *,
    symbols_csv: str | None,
    candidates_csv: Path,
    context_csv: Path,
    spotgamma_root: Path,
    max_symbols: int,
    limit: int | None,
) -> tuple[list[PaperLiveSymbolSpec], str]:
    cap = max_symbols
    if limit is not None and limit > 0:
        cap = min(cap, limit)

    if symbols_csv:
        symbols = [s.strip().upper() for s in symbols_csv.split(",") if s.strip()]
        symbols = symbols[:cap]
        if not symbols:
            raise SystemExit("NO_SYMBOL_SOURCE: --symbols was empty after parsing")
        by_sym = _latest_candidate_price_by_symbol(
            _optional_replay_candidates(candidates_csv, spotgamma_root)
        )
        specs: list[PaperLiveSymbolSpec] = []
        for sym in symbols:
            cand = by_sym.get(sym)
            price = cand.current_price if cand is not None else None
            specs.append(
                PaperLiveSymbolSpec(
                    symbol=sym,
                    current_price=price if price is not None and price > 0 else None,
                    source_profile=cand.source_profile if cand else "explicit_symbol",
                    has_spy_context=cand.has_spy_context if cand else False,
                    provenance=PAPER_LIVE_PROVENANCE,
                )
            )
        return specs, "explicit_symbols"

    if not context_csv.is_file() and not spotgamma_root.is_dir():
        raise SystemExit("NO_SYMBOL_SOURCE: provide --symbols or SpotGamma corpus (context/candidates)")

    freshness = assess_context_csv_freshness(context_csv) if context_csv.is_file() else None
    if context_csv.is_file() and freshness is not None and not freshness.is_fresh:
        raise SystemExit("NO_SYMBOL_SOURCE: SpotGamma context CSV is stale; rebuild corpus or pass --symbols")

    candidates, cand_source = load_replay_candidates(
        input_csv=candidates_csv,
        spotgamma_root=spotgamma_root,
        rebuild_if_missing=True,
    )
    by_sym = _latest_candidate_price_by_symbol(candidates)
    ordered = sorted(by_sym.keys())[:cap]
    if not ordered:
        raise SystemExit("NO_SYMBOL_SOURCE: no symbols in SpotGamma replay candidates")
    specs = []
    for sym in ordered:
        cand = by_sym[sym]
        price = cand.current_price
        specs.append(
            PaperLiveSymbolSpec(
                symbol=sym,
                current_price=price if price is not None and price > 0 else None,
                source_profile=cand.source_profile,
                has_spy_context=cand.has_spy_context,
                provenance=f"{PAPER_LIVE_PROVENANCE}|{cand_source}",
            )
        )
    return specs, f"spotgamma_corpus|{cand_source}"


def try_fetch_stock_mid_price(_option_client: Any, symbol: str) -> float | None:
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestQuoteRequest
    except ImportError:
        return None
    keys = resolve_market_data_api_keys()
    if keys is None:
        return None
    api_key, secret_key = keys
    try:
        stock_client = StockHistoricalDataClient(api_key=api_key, secret_key=secret_key, raw_data=True)
        raw = stock_client.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=symbol.strip().upper()))
    except Exception:
        return None
    quote = raw.get(symbol.strip().upper()) if isinstance(raw, dict) else raw
    if quote is None:
        return None
    if isinstance(quote, dict):
        bid = _float_or_none(quote.get("bp") or quote.get("bid_price"))
        ask = _float_or_none(quote.get("ap") or quote.get("ask_price"))
    else:
        bid = _float_or_none(getattr(quote, "bid_price", None))
        ask = _float_or_none(getattr(quote, "ask_price", None))
    if bid is not None and ask is not None and ask >= bid:
        return (bid + ask) / 2.0
    return bid or ask


def build_paper_live_blueprint_plans(
    specs: list[PaperLiveSymbolSpec],
    *,
    dte_min: int,
    dte_max: int,
    strike_buffer_pct: float,
    fetch_prices: bool,
    option_client: Any | None,
) -> list[AlpacaBlueprintReplayPlanRow]:
    trade_date = _today_trade_date()
    exp_window = expiration_window_label(trade_date, dte_min, dte_max)
    plans: list[AlpacaBlueprintReplayPlanRow] = []
    for spec in specs:
        price = spec.current_price
        if (price is None or price <= 0) and fetch_prices and option_client is not None:
            fetched = try_fetch_stock_mid_price(option_client, spec.symbol)
            if fetched is not None and fetched > 0:
                price = fetched
        if price is None or price <= 0:
            continue
        lower, upper = strike_bounds(price, strike_buffer_pct)
        plans.append(
            AlpacaBlueprintReplayPlanRow(
                symbol=spec.symbol,
                trade_date=trade_date,
                current_price=price,
                dte_min=dte_min,
                dte_max=dte_max,
                expiration_window=exp_window,
                strike_lower_bound=lower,
                strike_upper_bound=upper,
                request_reason="paper_live_current_chain",
                source_profile=spec.source_profile,
                has_spy_context=spec.has_spy_context,
                provenance=spec.provenance,
                databento_next_step="paper_live_no_databento",
            )
        )
    return plans


def _cap_contracts_per_symbol(
    rows: list[AlpacaGreeksCandidateRow],
    max_per_symbol: int | None,
) -> list[AlpacaGreeksCandidateRow]:
    if max_per_symbol is None or max_per_symbol <= 0:
        return rows
    by_sym: dict[str, list[AlpacaGreeksCandidateRow]] = {}
    for row in rows:
        sym = row.underlying_symbol.strip().upper()
        by_sym.setdefault(sym, []).append(row)
    out: list[AlpacaGreeksCandidateRow] = []
    for sym in sorted(by_sym.keys()):
        chunk = sorted(by_sym[sym], key=lambda r: r.option_symbol)[:max_per_symbol]
        out.extend(chunk)
    return out


def stage_greeks_paper_live(
    specs: list[PaperLiveSymbolSpec],
    *,
    symbol_source: str,
    fetch: bool,
    client: Any | None,
    dte_min: int,
    dte_max: int,
    strike_buffer_pct: float,
    risk_free_rate: float,
    allow_bs_fallback: bool,
    fallback_volatility_proxy: float | None,
    min_time_to_expiry_days: float | None,
    max_contracts_per_symbol: int | None,
) -> tuple[list[AlpacaGreeksCandidateRow], bool, GreeksFetchDiagnostics | None, list[AlpacaBlueprintReplayPlanRow]]:
    symbols = tuple(s.symbol for s in specs)
    plans = build_paper_live_blueprint_plans(
        specs,
        dte_min=dte_min,
        dte_max=dte_max,
        strike_buffer_pct=strike_buffer_pct,
        fetch_prices=fetch,
        option_client=client,
    )
    if not plans and fetch:
        diag = GreeksFetchDiagnostics(
            fetch_attempted=False,
            blueprint_rows=0,
            requests_attempted=0,
            requests_empty=0,
            requests_error=0,
            requests_invalid=len(specs),
            contracts_before_filter=0,
            contracts_removed_by_filter=0,
            contracts_after_filter=0,
            contracts_staged=0,
            request_descriptors=tuple(),
            empty_response_reasons=tuple(),
            error_summaries=("REQUEST_INVALID:missing_current_price",),
            failure_class="REQUEST_INVALID",
            staging_mode=PAPER_LIVE_MODE,
            symbols_requested=symbols,
            symbol_source=symbol_source,
        )
        return [], False, diag, plans
    rows, attempted, diag = stage_greeks_for_plans(
        plans,
        fetch=fetch and client is not None,
        client=client,
        risk_free_rate=risk_free_rate,
        allow_bs_fallback=allow_bs_fallback,
        fallback_volatility_proxy=fallback_volatility_proxy,
        min_time_to_expiry_days=min_time_to_expiry_days,
        row_mode=PAPER_LIVE_MODE,
        row_source=PAPER_LIVE_ROW_SOURCE,
        diagnostics_mode=PAPER_LIVE_MODE,
        symbols_requested=symbols,
        symbol_source=symbol_source,
    )
    rows = _cap_contracts_per_symbol(rows, max_contracts_per_symbol)
    if diag is not None and max_contracts_per_symbol:
        diag = replace(diag, contracts_staged=len(rows))
    return rows, attempted, diag, plans


def _parse_expiration_window(expiration_window: str) -> tuple[date, date]:
    parts = expiration_window.strip().split("..")
    if len(parts) != 2:
        raise ValueError(f"invalid expiration_window: {expiration_window!r}")
    return date.fromisoformat(parts[0].strip()), date.fromisoformat(parts[1].strip())


def _years_to_expiry(trade_date: str, expiration: str) -> float:
    td = date.fromisoformat(trade_date.strip())
    exp = date.fromisoformat(expiration.strip())
    return (exp - td).days / 365.25


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def compute_bsm_greeks(
    *,
    underlying_price: float,
    strike: float,
    time_years: float,
    risk_free_rate: float,
    implied_volatility: float,
    option_type: str,
) -> dict[str, float]:
    if time_years <= 0 or implied_volatility <= 0 or underlying_price <= 0 or strike <= 0:
        raise ValueError("invalid BSM inputs")
    sigma = implied_volatility
    t = time_years
    r = risk_free_rate
    s = underlying_price
    k = strike
    sqrt_t = math.sqrt(t)
    d1 = (math.log(s / k) + (r + 0.5 * sigma * sigma) * t) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t
    pdf_d1 = _norm_pdf(d1)
    if option_type == "call":
        delta = _norm_cdf(d1)
        theta = (
            -(s * pdf_d1 * sigma) / (2.0 * sqrt_t)
            - r * k * math.exp(-r * t) * _norm_cdf(d2)
        ) / 365.25
        rho = k * t * math.exp(-r * t) * _norm_cdf(d2) / 100.0
    elif option_type == "put":
        delta = _norm_cdf(d1) - 1.0
        theta = (
            -(s * pdf_d1 * sigma) / (2.0 * sqrt_t)
            + r * k * math.exp(-r * t) * _norm_cdf(-d2)
        ) / 365.25
        rho = -k * t * math.exp(-r * t) * _norm_cdf(-d2) / 100.0
    else:
        raise ValueError(f"unknown option_type: {option_type!r}")
    gamma = pdf_d1 / (s * sigma * sqrt_t)
    vega = s * pdf_d1 * sqrt_t / 100.0
    return {
        "delta": delta,
        "gamma": gamma,
        "theta": theta,
        "vega": vega,
        "rho": rho,
    }


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _extract_quote(snap: dict[str, Any]) -> tuple[float | None, float | None, float | None]:
    quote = snap.get("latestQuote") or snap.get("latest_quote") or {}
    if not isinstance(quote, dict):
        quote = {}
    bid = _float_or_none(quote.get("bp") or quote.get("bid_price"))
    ask = _float_or_none(quote.get("ap") or quote.get("ask_price"))
    mid = None
    if bid is not None and ask is not None:
        mid = (bid + ask) / 2.0
    return bid, ask, mid


def _extract_latest_trade(snap: dict[str, Any]) -> float | None:
    trade = snap.get("latestTrade") or snap.get("latest_trade") or {}
    if not isinstance(trade, dict):
        return None
    return _float_or_none(trade.get("p") or trade.get("price"))


def _extract_iv(snap: dict[str, Any]) -> float | None:
    return _float_or_none(
        snap.get("impliedVolatility")
        or snap.get("implied_volatility")
        or snap.get("iv")
    )


def _extract_alpaca_greeks(snap: dict[str, Any]) -> dict[str, float | None]:
    g = snap.get("greeks") or snap.get("Greeks") or {}
    if not isinstance(g, dict):
        g = {}
    return {
        "delta": _float_or_none(g.get("delta")),
        "gamma": _float_or_none(g.get("gamma")),
        "theta": _float_or_none(g.get("theta")),
        "vega": _float_or_none(g.get("vega")),
        "rho": _float_or_none(g.get("rho")),
    }


def _alpaca_greeks_complete(g: dict[str, float | None]) -> bool:
    return g.get("delta") is not None and g.get("gamma") is not None


def _filter_chain_snapshots_with_stats(
    snapshots: dict[str, Any],
    plan: AlpacaBlueprintReplayPlanRow,
) -> tuple[dict[str, Any], _ChainFilterStats]:
    exp_lo, exp_hi = _parse_expiration_window(plan.expiration_window)
    filtered: dict[str, Any] = {}
    removed_dte = 0
    removed_strike = 0
    for contract_symbol, snap in snapshots.items():
        if not isinstance(snap, dict):
            continue
        try:
            expiration, strike, option_type = parse_occ_us_option_contract(str(contract_symbol))
        except ValueError:
            continue
        if option_type not in {"call", "put"}:
            continue
        exp_d = date.fromisoformat(expiration)
        if exp_d < exp_lo or exp_d > exp_hi:
            removed_dte += 1
            continue
        if strike < plan.strike_lower_bound or strike > plan.strike_upper_bound:
            removed_strike += 1
            continue
        filtered[str(contract_symbol)] = snap
    return filtered, _ChainFilterStats(removed_by_dte=removed_dte, removed_by_strike=removed_strike)


def _effective_time_years(
    trade_date: str,
    expiration: str,
    *,
    min_time_to_expiry_days: float | None,
) -> tuple[float | None, GreeksStatus | None]:
    t = _years_to_expiry(trade_date, expiration)
    if t <= 0.0:
        if min_time_to_expiry_days is None:
            return None, "INVALID_INPUTS"
        floor = min_time_to_expiry_days / 365.25
        if floor <= 0.0:
            return None, "INVALID_INPUTS"
        return floor, None
    return t, None


def enrich_contract_row(
    *,
    plan: AlpacaBlueprintReplayPlanRow,
    option_symbol: str,
    expiration: str,
    strike: float,
    option_type: str,
    snap: dict[str, Any] | None,
    risk_free_rate: float,
    allow_bs_fallback: bool,
    fallback_volatility_proxy: float | None,
    min_time_to_expiry_days: float | None,
    row_mode: str = HISTORICAL_REPLAY_MODE,
    row_source: str = "alpaca_greeks_c1_staging",
) -> AlpacaGreeksCandidateRow:
    bid, ask, mid = (None, None, None)
    latest_trade = None
    iv = None
    greeks = {"delta": None, "gamma": None, "theta": None, "vega": None, "rho": None}
    source: GreeksSource = "missing"
    status: GreeksStatus = "MISSING"
    confidence: GreeksConfidence = "none"
    vol_proxy = False

    if snap is not None:
        bid, ask, mid = _extract_quote(snap)
        latest_trade = _extract_latest_trade(snap)
        iv = _extract_iv(snap)
        greeks = _extract_alpaca_greeks(snap)

    if bid is None or ask is None:
        return AlpacaGreeksCandidateRow(
            underlying_symbol=plan.symbol,
            trade_date=plan.trade_date,
            current_price=plan.current_price,
            option_symbol=option_symbol,
            expiration=expiration,
            strike=strike,
            option_type=option_type,
            bid=bid,
            ask=ask,
            mid=mid,
            latest_trade=latest_trade,
            delta=greeks["delta"],
            gamma=greeks["gamma"],
            theta=greeks["theta"],
            vega=greeks["vega"],
            rho=greeks["rho"],
            implied_volatility=iv,
            greeks_source="missing",
            greeks_status="INVALID_INPUTS",
            greeks_confidence="none",
            volatility_is_proxy=False,
            provenance=PROVENANCE_TAG,
            blueprint_provenance=plan.provenance,
            source_profile=plan.source_profile,
            has_spy_context=plan.has_spy_context,
            mode=row_mode,
            source=row_source,
        )
    if _alpaca_greeks_complete(greeks):
        source = "alpaca_snapshot"
        status = "AVAILABLE"
        confidence = "high"
    elif allow_bs_fallback:
        sigma = iv
        if sigma is None and fallback_volatility_proxy is not None and fallback_volatility_proxy > 0:
            sigma = fallback_volatility_proxy
            vol_proxy = True
        if sigma is None:
            status = "MISSING"
        else:
            t_eff, invalid = _effective_time_years(
                plan.trade_date,
                expiration,
                min_time_to_expiry_days=min_time_to_expiry_days,
            )
            if invalid is not None:
                status = invalid
            elif t_eff is None:
                status = "MISSING"
            else:
                try:
                    computed = compute_bsm_greeks(
                        underlying_price=plan.current_price,
                        strike=strike,
                        time_years=t_eff,
                        risk_free_rate=risk_free_rate,
                        implied_volatility=sigma,
                        option_type=option_type,
                    )
                    greeks = {k: computed[k] for k in greeks}
                    source = "computed_bs"
                    status = "COMPUTED"
                    confidence = "medium" if not vol_proxy else "low"
                    if iv is None:
                        iv = sigma
                except ValueError:
                    status = "INVALID_INPUTS"
    else:
        status = "MISSING"

    return AlpacaGreeksCandidateRow(
        underlying_symbol=plan.symbol,
        trade_date=plan.trade_date,
        current_price=plan.current_price,
        option_symbol=option_symbol,
        expiration=expiration,
        strike=strike,
        option_type=option_type,
        bid=bid,
        ask=ask,
        mid=mid,
        latest_trade=latest_trade,
        delta=greeks["delta"],
        gamma=greeks["gamma"],
        theta=greeks["theta"],
        vega=greeks["vega"],
        rho=greeks["rho"],
        implied_volatility=iv,
        greeks_source=source,
        greeks_status=status,
        greeks_confidence=confidence,
        volatility_is_proxy=vol_proxy,
        provenance=PROVENANCE_TAG,
        blueprint_provenance=plan.provenance,
        source_profile=plan.source_profile,
        has_spy_context=plan.has_spy_context,
        mode=row_mode,
        source=row_source,
    )


def fetch_alpaca_chain_snapshots(
    client: Any,
    plan: AlpacaBlueprintReplayPlanRow,
) -> dict[str, Any]:
    result = _fetch_option_chain_attempt(client, plan)
    return result.filtered_snapshots


def _fetch_option_chain_attempt(client: Any, plan: AlpacaBlueprintReplayPlanRow) -> _FetchAttemptResult:
    valid, reason = validate_blueprint_for_chain_request(plan)
    if not valid:
        return _FetchAttemptResult(
            outcome="invalid",
            contracts_before_filter=0,
            contracts_after_filter=0,
            filtered_snapshots={},
            empty_reason=None,
            error_summary=f"REQUEST_INVALID:{reason}",
        )
    from alpaca.data.requests import OptionChainRequest

    exp_lo, exp_hi = _parse_expiration_window(plan.expiration_window)
    request = OptionChainRequest(
        underlying_symbol=plan.symbol.strip().upper(),
        expiration_date_gte=exp_lo,
        expiration_date_lte=exp_hi,
    )
    try:
        raw = client.get_option_chain(request)
    except AttributeError as exc:
        return _FetchAttemptResult(
            outcome="error",
            contracts_before_filter=0,
            contracts_after_filter=0,
            filtered_snapshots={},
            empty_reason=None,
            error_summary=f"CLIENT_METHOD_UNSUPPORTED:{type(exc).__name__}",
        )
    except Exception as exc:
        failure = _classify_fetch_exception(exc)
        return _FetchAttemptResult(
            outcome="error",
            contracts_before_filter=0,
            contracts_after_filter=0,
            filtered_snapshots={},
            empty_reason=None,
            error_summary=f"{failure}:{type(exc).__name__}",
        )
    if not isinstance(raw, dict):
        return _FetchAttemptResult(
            outcome="error",
            contracts_before_filter=0,
            contracts_after_filter=0,
            filtered_snapshots={},
            empty_reason=None,
            error_summary=f"API_SHAPE_MISMATCH:expected_dict_got_{type(raw).__name__}",
        )
    before = len(raw)
    filtered, stats = _filter_chain_snapshots_with_stats(raw, plan)
    after = len(filtered)
    if before == 0:
        return _FetchAttemptResult(
            outcome="empty",
            contracts_before_filter=0,
            contracts_after_filter=0,
            filtered_snapshots={},
            empty_reason="alpaca_returned_zero_contracts",
            error_summary=None,
        )
    if after == 0:
        return _FetchAttemptResult(
            outcome="empty",
            contracts_before_filter=before,
            contracts_after_filter=0,
            filtered_snapshots={},
            empty_reason="filter_removed_all_contracts",
            error_summary=None,
            removed_by_dte=stats.removed_by_dte,
            removed_by_strike=stats.removed_by_strike,
        )
    return _FetchAttemptResult(
        outcome="ok",
        contracts_before_filter=before,
        contracts_after_filter=after,
        filtered_snapshots=filtered,
        empty_reason=None,
        error_summary=None,
        removed_by_dte=stats.removed_by_dte,
        removed_by_strike=stats.removed_by_strike,
    )


def stage_greeks_for_plans(
    plans: list[AlpacaBlueprintReplayPlanRow],
    *,
    fetch: bool,
    client: Any | None,
    risk_free_rate: float,
    allow_bs_fallback: bool,
    fallback_volatility_proxy: float | None,
    min_time_to_expiry_days: float | None,
    row_mode: str = HISTORICAL_REPLAY_MODE,
    row_source: str = "alpaca_greeks_c1_staging",
    diagnostics_mode: str = HISTORICAL_REPLAY_MODE,
    symbols_requested: tuple[str, ...] = (),
    symbol_source: str = "",
) -> tuple[list[AlpacaGreeksCandidateRow], bool, GreeksFetchDiagnostics | None]:
    rows: list[AlpacaGreeksCandidateRow] = []
    if not fetch:
        return rows, False, None
    if client is None:
        return rows, False, None

    descriptors: list[dict[str, object]] = []
    empty_reasons: list[str] = []
    error_summaries: list[str] = []
    requests_attempted = 0
    requests_empty = 0
    requests_error = 0
    requests_invalid = 0
    contracts_before = 0
    contracts_after = 0
    removed_dte_total = 0
    removed_strike_total = 0

    for plan in plans:
        if len(descriptors) < 3:
            descriptors.append(sanitize_blueprint_descriptor(plan))
        attempt = _fetch_option_chain_attempt(client, plan)
        if attempt.outcome == "invalid":
            requests_invalid += 1
            if attempt.error_summary and len(error_summaries) < 3:
                error_summaries.append(attempt.error_summary)
            continue
        requests_attempted += 1
        contracts_before += attempt.contracts_before_filter
        contracts_after += attempt.contracts_after_filter
        removed_dte_total += attempt.removed_by_dte
        removed_strike_total += attempt.removed_by_strike
        if attempt.outcome == "error":
            requests_error += 1
            if attempt.error_summary and len(error_summaries) < 3:
                error_summaries.append(attempt.error_summary)
            continue
        if attempt.outcome == "empty":
            requests_empty += 1
            if attempt.empty_reason and len(empty_reasons) < 3:
                tag = f"{plan.symbol}:{attempt.empty_reason}"
                empty_reasons.append(tag)
            continue
        snapshots = attempt.filtered_snapshots
        for option_symbol, snap in sorted(snapshots.items()):
            try:
                expiration, strike, option_type = parse_occ_us_option_contract(option_symbol)
            except ValueError:
                continue
            rows.append(
                enrich_contract_row(
                    plan=plan,
                    option_symbol=option_symbol,
                    expiration=expiration,
                    strike=strike,
                    option_type=option_type,
                    snap=snap,
                    risk_free_rate=risk_free_rate,
                    allow_bs_fallback=allow_bs_fallback,
                    fallback_volatility_proxy=fallback_volatility_proxy,
                    min_time_to_expiry_days=min_time_to_expiry_days,
                    row_mode=row_mode,
                    row_source=row_source,
                )
            )

    diag = GreeksFetchDiagnostics(
        fetch_attempted=True,
        blueprint_rows=len(plans),
        requests_attempted=requests_attempted,
        requests_empty=requests_empty,
        requests_error=requests_error,
        requests_invalid=requests_invalid,
        contracts_before_filter=contracts_before,
        contracts_removed_by_filter=max(0, contracts_before - contracts_after),
        contracts_after_filter=contracts_after,
        contracts_staged=len(rows),
        request_descriptors=tuple(descriptors[:3]),
        empty_response_reasons=tuple(empty_reasons[:3]),
        error_summaries=tuple(error_summaries[:3]),
        failure_class=None,
        staging_mode=diagnostics_mode,
        symbols_requested=symbols_requested,
        symbol_source=symbol_source,
        contracts_removed_by_dte_filter=removed_dte_total,
        contracts_removed_by_strike_filter=removed_strike_total,
    )
    failure = resolve_fetch_failure_class(diag)
    diag = replace(diag, failure_class=failure)
    return rows, True, diag


def greeks_candidates_to_dataframe(rows: list[AlpacaGreeksCandidateRow]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=[f.name for f in fields(AlpacaGreeksCandidateRow)])
    return pd.DataFrame([{f.name: getattr(r, f.name) for f in fields(AlpacaGreeksCandidateRow)} for r in rows])


def summarize_greeks_staging(
    blueprint_row_count: int,
    candidates: list[AlpacaGreeksCandidateRow],
    *,
    fetch_attempted: bool,
) -> dict[str, object]:
    source_counts: dict[str, int] = {"alpaca_snapshot": 0, "computed_bs": 0, "missing": 0}
    status_counts: dict[str, int] = {
        "AVAILABLE": 0,
        "COMPUTED": 0,
        "MISSING": 0,
        "INVALID_INPUTS": 0,
    }
    for row in candidates:
        source_counts[row.greeks_source] = source_counts.get(row.greeks_source, 0) + 1
        status_counts[row.greeks_status] = status_counts.get(row.greeks_status, 0) + 1
    return {
        "blueprint_input_rows": blueprint_row_count,
        "greeks_candidate_rows": len(candidates),
        "fetch_attempted": fetch_attempted,
        "greeks_source_counts": source_counts,
        "greeks_status_counts": status_counts,
        "missing_or_invalid_count": status_counts["MISSING"] + status_counts["INVALID_INPUTS"],
    }


CredentialStatus = Literal["READY", "MISSING"]


@dataclass(frozen=True, slots=True)
class AlpacaMarketDataCredentialCheck:
    """Read-only market-data credential readiness (no secret values)."""

    credential_status: CredentialStatus
    env_pair_label: str | None
    detail: str | None


def repo_root_env_path() -> Path:
    """Path to repo-root `.env` (never read or printed by callers)."""
    return Path(__file__).resolve().parents[3] / ".env"


_HYDRATION_SAFE_ENV_FLAGS: tuple[str, ...] = ("NO_SUBMIT", "DRY_RUN", "PAPER_ONLY")
_HYDRATION_SAFE_TRUTHY = frozenset({"1", "true", "yes", "on"})


def load_local_env(*, env_path: Path | None = None) -> bool:
    """
    Load local `.env` when python-dotenv is available.

    Does not override already-exported environment variables. Never raises on
    permission errors; never logs values.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return False
    path = env_path if env_path is not None else repo_root_env_path()
    if not path.is_file():
        return False
    try:
        load_dotenv(path, override=False)
    except PermissionError:
        return False
    return True


def validate_hydration_safety_env() -> str | None:
    """
    When NO_SUBMIT / DRY_RUN / PAPER_ONLY are set, they must be fail-closed safe.

    Missing flags preserve existing safe defaults (hydration remains read-only).
    """
    for name in _HYDRATION_SAFE_ENV_FLAGS:
        raw = os.environ.get(name)
        if raw is None:
            continue
        normalized = str(raw).strip().lower()
        if not normalized:
            continue
        if normalized in _HYDRATION_SAFE_TRUTHY:
            continue
        return f"preflight_error:unsafe_env_flag:{name}"
    return None


def preflight_hydration_auth() -> str | None:
    """Load repo `.env` then validate optional hydration safety flags."""
    load_local_env()
    return validate_hydration_safety_env()


def _env_nonempty(name: str) -> str | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    value = str(raw).strip()
    return value if value else None


def check_alpaca_market_data_credentials() -> AlpacaMarketDataCredentialCheck:
    """
    Detect one complete Alpaca market-data key pair (never logs values).

    Supports ALPACA_API_KEY + ALPACA_SECRET_KEY or APCA_API_KEY_ID + APCA_API_SECRET_KEY.
    """
    pairs: tuple[tuple[str, str, str], ...] = (
        ("ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ALPACA_*"),
        ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY", "APCA_*"),
    )
    for key_name, secret_name, label in pairs:
        key = _env_nonempty(key_name)
        secret = _env_nonempty(secret_name)
        if key and secret:
            return AlpacaMarketDataCredentialCheck(
                credential_status="READY",
                env_pair_label=label,
                detail=None,
            )
        if key or secret:
            return AlpacaMarketDataCredentialCheck(
                credential_status="MISSING",
                env_pair_label=label,
                detail="incomplete_credential_pair",
            )
    return AlpacaMarketDataCredentialCheck(
        credential_status="MISSING",
        env_pair_label=None,
        detail="no_credential_pair",
    )


def resolve_market_data_api_keys() -> tuple[str, str] | None:
    """Return (api_key, secret_key) for read-only market data when a full pair exists."""
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


def try_create_option_client() -> tuple[Any | None, str | None]:
    load_local_env()
    creds = check_alpaca_market_data_credentials()
    if creds.credential_status != "READY":
        detail = creds.detail or "missing_credentials"
        return None, f"credential_error:{detail}"
    try:
        from alpaca.data.historical.option import OptionHistoricalDataClient
    except ImportError as exc:
        return None, f"import_error:{exc}"
    keys = resolve_market_data_api_keys()
    if keys is None:
        return None, "credential_error:no_credential_pair"
    api_key, secret_key = keys
    try:
        return (
            OptionHistoricalDataClient(api_key=api_key, secret_key=secret_key, raw_data=True),
            None,
        )
    except ValueError as exc:
        return None, f"credential_error:{exc}"
    except Exception as exc:
        return None, f"client_error:{type(exc).__name__}"
