"""Generate math-gated vertical spread candidates from staged Alpaca greeks/quote rows."""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from datetime import date
from pathlib import Path

import pandas as pd

from qops.backtest.alpaca_greeks_layer import AlpacaGreeksCandidateRow
from qops.schemas.candidate import ScreenedCandidate
from qops.schemas.environment import (
    DirectionalBias,
    IVState,
    RegimeLabel,
    SkewState,
    WallState,
)
from qops.schemas.playbook import AllowedPlaybook, StructureBias
from qops.signals.classifier import (
    GammaRegimeState,
    PremiumPosture,
    SignalType,
    VolTriggerRelation,
)
from qops.strategy.constants import (
    DEFAULT_BEAR_CALL_CREDIT_WIDTH,
    DEFAULT_BEAR_PUT_WIDTH,
    DEFAULT_BULL_CALL_WIDTH,
    DEFAULT_BULL_PUT_CREDIT_WIDTH,
    MIN_DTE,
)
from qops.strategy.spread_builder import build_structure_candidate
from qops.strategy.spread_math import SpreadMathEvaluation, SpreadMathInputs, evaluate_spread_math

PROVENANCE_TAG = "struct_c2_spread_candidate_generation"

ALL_STRUCTURES: frozenset[str] = frozenset(
    {
        AllowedPlaybook.BULL_CALL_SPREAD.value,
        AllowedPlaybook.BEAR_PUT_SPREAD.value,
        AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value,
        AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD.value,
    }
)


@dataclass(frozen=True, slots=True)
class StagedGreeksQuoteRow:
    """Greeks/quote row plus optional PMP from staging CSV (never fabricated)."""

    quote: AlpacaGreeksCandidateRow
    probability_of_profit: float | None


@dataclass(frozen=True, slots=True)
class GeneratedSpreadCandidate:
    """One vertical spread candidate after quote pairing and spread math."""

    structure_type: str
    underlying_symbol: str
    trade_date: str
    expiration: str
    long_option_symbol: str
    short_option_symbol: str
    spread_width: float
    net_debit_or_credit: float
    reference_strike: float
    probability_of_profit: float | None
    math: SpreadMathEvaluation
    candidate_pass: bool
    builder_succeeded: bool
    failure_reasons: tuple[str, ...]
    provenance: str
    greeks_provenance: str


def load_greeks_quote_rows(path: str | Path) -> list[StagedGreeksQuoteRow]:
    p = Path(path)
    if not p.is_file():
        return []
    df = pd.read_csv(p)
    out: list[StagedGreeksQuoteRow] = []
    for _, series in df.iterrows():
        kwargs: dict[str, object] = {}
        for f in fields(AlpacaGreeksCandidateRow):
            name = f.name
            raw = series[name] if name in series.index else None
            if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                if name == "has_spy_context":
                    kwargs[name] = False
                elif name == "current_price":
                    kwargs[name] = None
                elif name in {"bid", "ask", "mid", "latest_trade", "delta", "gamma", "theta", "vega", "rho"}:
                    kwargs[name] = None
                elif name == "implied_volatility":
                    kwargs[name] = None
                elif name == "volatility_is_proxy":
                    kwargs[name] = False
                else:
                    kwargs[name] = ""
                continue
            if name == "has_spy_context":
                kwargs[name] = str(raw).strip().lower() in {"1", "true", "yes"} if not isinstance(raw, bool) else raw
            elif name == "volatility_is_proxy":
                kwargs[name] = str(raw).strip().lower() in {"1", "true", "yes"} if not isinstance(raw, bool) else raw
            elif name in {"current_price", "strike"}:
                kwargs[name] = float(raw)
            elif name in {"bid", "ask", "mid", "latest_trade", "delta", "gamma", "theta", "vega", "rho", "implied_volatility"}:
                kwargs[name] = float(raw)
            else:
                kwargs[name] = str(raw).strip()
        if kwargs.get("current_price") is None:
            continue
        pmp_raw = series.get("probability_of_profit") if "probability_of_profit" in series.index else None
        pmp: float | None = None
        if pmp_raw is not None and not (isinstance(pmp_raw, float) and pd.isna(pmp_raw)):
            pmp = float(pmp_raw)
        out.append(
            StagedGreeksQuoteRow(
                quote=AlpacaGreeksCandidateRow(**kwargs),  # type: ignore[arg-type]
                probability_of_profit=pmp,
            )
        )
    return out


def _dte_between(trade_date: str, expiration: str) -> int:
    td = date.fromisoformat(trade_date.strip())
    exp = date.fromisoformat(expiration.strip())
    return max(0, (exp - td).days)


def _quotes_liquid(bid: float | None, ask: float | None, *, max_bid_ask_spread_pct: float) -> bool:
    if bid is None or ask is None:
        return False
    if bid <= 0 or ask <= 0 or ask < bid:
        return False
    mid = (bid + ask) / 2.0
    if mid <= 0:
        return False
    return (ask - bid) / mid <= max_bid_ask_spread_pct


def _screened_envelope_for_builder(
    *,
    quote_row: AlpacaGreeksCandidateRow,
    playbook: AllowedPlaybook,
    expiration: str,
) -> ScreenedCandidate:
    dte = _dte_between(quote_row.trade_date, expiration)
    if dte < MIN_DTE:
        dte = MIN_DTE
    return ScreenedCandidate(
        symbol=quote_row.underlying_symbol.strip().upper(),
        underlying_price=quote_row.current_price,
        dte_target=dte,
        expiry_target=expiration,
        regime_label=RegimeLabel.NEUTRAL,
        structure_bias=StructureBias(playbook.value),
        confidence=0,
        gamma_ratio=None,
        iv_rank=0.0,
        iv_state=IVState.MID_VOL,
        rr_rank=0.0,
        skew_state=SkewState.NEUTRAL,
        iv_1m=0.0,
        rv_1m=0.0,
        vrp=0.0,
        vrp_z=None,
        call_wall=None,
        put_wall=None,
        wall_state=WallState.UNKNOWN,
        directional_bias=DirectionalBias.NEUTRAL_BIAS,
        signal_type=SignalType.NONE,
        signal_horizon_days=(0, 999),
        wall_distance_pct=None,
        signal_strength="UNKNOWN",
        vol_trigger=None,
        vol_trigger_relation=VolTriggerRelation.UNKNOWN,
        gamma_regime_state=GammaRegimeState.UNKNOWN,
        premium_posture=PremiumPosture.UNKNOWN,
        dte_alignment_pass=True,
        allowed_playbook=playbook,
        tradeability_pass=True,
        liquidity_pass=True,
        screener_reason=f"{PROVENANCE_TAG}|envelope_from_greeks_staging_only",
        skip_reason=None,
    )


def _default_width_for_playbook(playbook: AllowedPlaybook) -> float:
    if playbook == AllowedPlaybook.BULL_CALL_SPREAD:
        return DEFAULT_BULL_CALL_WIDTH
    if playbook == AllowedPlaybook.BEAR_PUT_SPREAD:
        return DEFAULT_BEAR_PUT_WIDTH
    if playbook == AllowedPlaybook.BULL_PUT_CREDIT_SPREAD:
        return DEFAULT_BULL_PUT_CREDIT_WIDTH
    return DEFAULT_BEAR_CALL_CREDIT_WIDTH


def _builder_applicable(playbook: AllowedPlaybook, spread_width: float) -> bool:
    """Builder scaffold uses fixed default widths; only invoke when quotes match."""
    return spread_width == _default_width_for_playbook(playbook)


def _candidate_pass(math: SpreadMathEvaluation, probability_of_profit: float | None) -> bool:
    if probability_of_profit is None:
        return False
    return math.passes_spread_math_gate


def _emit_candidate(
    *,
    structure_type: str,
    playbook: AllowedPlaybook,
    long_row: StagedGreeksQuoteRow,
    short_row: StagedGreeksQuoteRow,
    spread_width: float,
    net_debit_or_credit: float,
    reference_strike: float,
    try_builder: bool,
) -> GeneratedSpreadCandidate | None:
    if spread_width <= 0 or net_debit_or_credit <= 0:
        return None
    if not math.isfinite(spread_width) or not math.isfinite(net_debit_or_credit):
        return None

    pmp = long_row.probability_of_profit if long_row.probability_of_profit is not None else short_row.probability_of_profit
    math_eval = evaluate_spread_math(
        SpreadMathInputs(
            structure_type=structure_type,
            spread_width=spread_width,
            net_debit_or_credit=net_debit_or_credit,
            reference_strike=reference_strike,
        ),
        probability_of_profit=pmp,
    )
    failure_reasons = list(math_eval.failure_reasons)
    builder_ok = False
    if try_builder and _builder_applicable(playbook, spread_width) and math_eval.passes_spread_math_gate:
        try:
            build_structure_candidate(
                _screened_envelope_for_builder(
                    quote_row=long_row.quote,
                    playbook=playbook,
                    expiration=long_row.quote.expiration,
                ),
                net_debit_or_credit,
                reference_strike=reference_strike,
                probability_of_profit=pmp,
            )
            builder_ok = True
        except ValueError as exc:
            failure_reasons.append(str(exc))

    passed = _candidate_pass(math_eval, pmp)
    if not passed and pmp is None and not failure_reasons:
        failure_reasons.append("missing_probability_of_profit")

    return GeneratedSpreadCandidate(
        structure_type=structure_type,
        underlying_symbol=long_row.quote.underlying_symbol,
        trade_date=long_row.quote.trade_date,
        expiration=long_row.quote.expiration,
        long_option_symbol=long_row.quote.option_symbol,
        short_option_symbol=short_row.quote.option_symbol,
        spread_width=spread_width,
        net_debit_or_credit=net_debit_or_credit,
        reference_strike=reference_strike,
        probability_of_profit=pmp,
        math=math_eval,
        candidate_pass=passed,
        builder_succeeded=builder_ok,
        failure_reasons=tuple(dict.fromkeys(failure_reasons)),
        provenance=PROVENANCE_TAG,
        greeks_provenance=long_row.quote.provenance,
    )


def _pair_bull_call(
    rows: list[StagedGreeksQuoteRow],
    *,
    max_bid_ask_spread_pct: float,
    try_builder: bool,
) -> list[GeneratedSpreadCandidate]:
    calls = sorted(
        [r for r in rows if r.quote.option_type == "call" and _quotes_liquid(r.quote.bid, r.quote.ask, max_bid_ask_spread_pct=max_bid_ask_spread_pct)],
        key=lambda r: r.quote.strike,
    )
    out: list[GeneratedSpreadCandidate] = []
    for i, long_row in enumerate(calls):
        for short_row in calls[i + 1 :]:
            width = short_row.quote.strike - long_row.quote.strike
            net_debit = float(long_row.quote.ask) - float(short_row.quote.bid)  # type: ignore[arg-type]
            cand = _emit_candidate(
                structure_type=AllowedPlaybook.BULL_CALL_SPREAD.value,
                playbook=AllowedPlaybook.BULL_CALL_SPREAD,
                long_row=long_row,
                short_row=short_row,
                spread_width=width,
                net_debit_or_credit=net_debit,
                reference_strike=long_row.quote.strike,
                try_builder=try_builder,
            )
            if cand is not None:
                out.append(cand)
    return out


def _pair_bear_put(
    rows: list[StagedGreeksQuoteRow],
    *,
    max_bid_ask_spread_pct: float,
    try_builder: bool,
) -> list[GeneratedSpreadCandidate]:
    puts = sorted(
        [r for r in rows if r.quote.option_type == "put" and _quotes_liquid(r.quote.bid, r.quote.ask, max_bid_ask_spread_pct=max_bid_ask_spread_pct)],
        key=lambda r: r.quote.strike,
    )
    out: list[GeneratedSpreadCandidate] = []
    for i, short_row in enumerate(puts):
        for long_row in puts[i + 1 :]:
            width = long_row.quote.strike - short_row.quote.strike
            net_debit = float(long_row.quote.ask) - float(short_row.quote.bid)  # type: ignore[arg-type]
            cand = _emit_candidate(
                structure_type=AllowedPlaybook.BEAR_PUT_SPREAD.value,
                playbook=AllowedPlaybook.BEAR_PUT_SPREAD,
                long_row=long_row,
                short_row=short_row,
                spread_width=width,
                net_debit_or_credit=net_debit,
                reference_strike=long_row.quote.strike,
                try_builder=try_builder,
            )
            if cand is not None:
                out.append(cand)
    return out


def _pair_bull_put_credit(
    rows: list[StagedGreeksQuoteRow],
    *,
    max_bid_ask_spread_pct: float,
    try_builder: bool,
) -> list[GeneratedSpreadCandidate]:
    puts = sorted(
        [r for r in rows if r.quote.option_type == "put" and _quotes_liquid(r.quote.bid, r.quote.ask, max_bid_ask_spread_pct=max_bid_ask_spread_pct)],
        key=lambda r: r.quote.strike,
    )
    out: list[GeneratedSpreadCandidate] = []
    for i, long_row in enumerate(puts):
        for short_row in puts[i + 1 :]:
            width = short_row.quote.strike - long_row.quote.strike
            net_credit = float(short_row.quote.bid) - float(long_row.quote.ask)  # type: ignore[arg-type]
            cand = _emit_candidate(
                structure_type=AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value,
                playbook=AllowedPlaybook.BULL_PUT_CREDIT_SPREAD,
                long_row=long_row,
                short_row=short_row,
                spread_width=width,
                net_debit_or_credit=net_credit,
                reference_strike=short_row.quote.strike,
                try_builder=try_builder,
            )
            if cand is not None:
                out.append(cand)
    return out


def _pair_bear_call_credit(
    rows: list[StagedGreeksQuoteRow],
    *,
    max_bid_ask_spread_pct: float,
    try_builder: bool,
) -> list[GeneratedSpreadCandidate]:
    calls = sorted(
        [r for r in rows if r.quote.option_type == "call" and _quotes_liquid(r.quote.bid, r.quote.ask, max_bid_ask_spread_pct=max_bid_ask_spread_pct)],
        key=lambda r: r.quote.strike,
    )
    out: list[GeneratedSpreadCandidate] = []
    for i, long_row in enumerate(calls):
        for short_row in calls[:i]:
            width = long_row.quote.strike - short_row.quote.strike
            net_credit = float(short_row.quote.bid) - float(long_row.quote.ask)  # type: ignore[arg-type]
            cand = _emit_candidate(
                structure_type=AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD.value,
                playbook=AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD,
                long_row=long_row,
                short_row=short_row,
                spread_width=width,
                net_debit_or_credit=net_credit,
                reference_strike=short_row.quote.strike,
                try_builder=try_builder,
            )
            if cand is not None:
                out.append(cand)
    return out


def _resolve_structures(structures: list[str] | None) -> frozenset[str]:
    if not structures or structures == ["ALL"] or "ALL" in structures:
        return ALL_STRUCTURES
    unknown = set(structures) - ALL_STRUCTURES
    if unknown:
        raise ValueError(f"unsupported structure filter: {sorted(unknown)}")
    return frozenset(structures)


def generate_spread_candidates(
    rows: list[StagedGreeksQuoteRow],
    *,
    structures: list[str] | None = None,
    max_bid_ask_spread_pct: float = 0.25,
    max_per_underlying_date: int | None = None,
    limit: int | None = None,
    try_builder: bool = True,
) -> list[GeneratedSpreadCandidate]:
    """Pair vertical spreads per underlying/trade_date/expiration and run spread math."""
    if max_bid_ask_spread_pct < 0:
        raise ValueError("max_bid_ask_spread_pct must be >= 0")
    wanted = _resolve_structures(structures)

    grouped: dict[tuple[str, str, str], list[StagedGreeksQuoteRow]] = {}
    for row in rows:
        key = (
            row.quote.underlying_symbol.strip().upper(),
            row.quote.trade_date.strip(),
            row.quote.expiration.strip(),
        )
        grouped.setdefault(key, []).append(row)

    generated: list[GeneratedSpreadCandidate] = []
    for key in sorted(grouped.keys()):
        group = grouped[key]
        batch: list[GeneratedSpreadCandidate] = []
        if AllowedPlaybook.BULL_CALL_SPREAD.value in wanted:
            batch.extend(_pair_bull_call(group, max_bid_ask_spread_pct=max_bid_ask_spread_pct, try_builder=try_builder))
        if AllowedPlaybook.BEAR_PUT_SPREAD.value in wanted:
            batch.extend(_pair_bear_put(group, max_bid_ask_spread_pct=max_bid_ask_spread_pct, try_builder=try_builder))
        if AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value in wanted:
            batch.extend(_pair_bull_put_credit(group, max_bid_ask_spread_pct=max_bid_ask_spread_pct, try_builder=try_builder))
        if AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD.value in wanted:
            batch.extend(_pair_bear_call_credit(group, max_bid_ask_spread_pct=max_bid_ask_spread_pct, try_builder=try_builder))
        if max_per_underlying_date is not None and max_per_underlying_date > 0:
            batch = batch[:max_per_underlying_date]
        generated.extend(batch)

    if limit is not None and limit > 0:
        generated = generated[:limit]
    return generated


def spread_candidates_to_dataframe(candidates: list[GeneratedSpreadCandidate]) -> pd.DataFrame:
    if not candidates:
        return pd.DataFrame()
    records: list[dict[str, object]] = []
    for c in candidates:
        records.append(
            {
                "structure_type": c.structure_type,
                "underlying_symbol": c.underlying_symbol,
                "trade_date": c.trade_date,
                "expiration": c.expiration,
                "long_option_symbol": c.long_option_symbol,
                "short_option_symbol": c.short_option_symbol,
                "spread_width": c.spread_width,
                "net_debit_or_credit": c.net_debit_or_credit,
                "reference_strike": c.reference_strike,
                "probability_of_profit": c.probability_of_profit,
                "reward_risk": c.math.reward_risk,
                "passes_spread_math_gate": c.math.passes_spread_math_gate,
                "probability_status": c.math.probability_status,
                "ev_status": c.math.ev_status,
                "candidate_pass": c.candidate_pass,
                "builder_succeeded": c.builder_succeeded,
                "failure_reasons": "|".join(c.failure_reasons),
                "provenance": c.provenance,
                "greeks_provenance": c.greeks_provenance,
            }
        )
    return pd.DataFrame(records)


def summarize_spread_generation(
    input_rows: int,
    candidates: list[GeneratedSpreadCandidate],
) -> dict[str, object]:
    failure_counts: dict[str, int] = {}
    for c in candidates:
        for reason in c.failure_reasons:
            failure_counts[reason] = failure_counts.get(reason, 0) + 1
    incomplete_pmp = sum(1 for c in candidates if c.probability_of_profit is None)
    passing = sum(1 for c in candidates if c.candidate_pass)
    math_pass = sum(1 for c in candidates if c.math.passes_spread_math_gate)
    return {
        "input_rows": input_rows,
        "spread_candidates_generated": len(candidates),
        "candidates_passing_math_gate": math_pass,
        "candidates_pass": passing,
        "candidates_incomplete_missing_pmp": incomplete_pmp,
        "failure_reason_counts": failure_counts,
    }
