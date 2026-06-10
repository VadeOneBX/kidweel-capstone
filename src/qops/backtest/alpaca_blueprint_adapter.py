"""Alpaca 0DTE backtest blueprint shape for SpotGamma replay (plan only, no fetch)."""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from qops.backtest.alpaca_replay_inputs import (
    AlpacaReplayInputPlanRow,
    build_availability_plan,
    load_replay_candidates,
)

PROVENANCE_TAG = "sg_bt_c4a_blueprint_replay_plan"
READY_STATUS = "READY_FOR_FETCH"
DATABENTO_NEXT_STEP = (
    "After Alpaca read-only chain collect returns OCC symbols within expiration_window "
    "and strike bounds, request Databento Greeks and bar slices for those contracts only. "
    "No bulk OPRA or full-surface pulls."
)


@dataclass(frozen=True, slots=True)
class AlpacaBlueprintReplayPlanRow:
    symbol: str
    trade_date: str
    current_price: float
    dte_min: int
    dte_max: int
    expiration_window: str
    strike_lower_bound: float
    strike_upper_bound: float
    request_reason: str
    source_profile: str
    has_spy_context: bool
    provenance: str
    databento_next_step: str


def load_availability_plan_from_csv(path: str | Path) -> list[AlpacaReplayInputPlanRow]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"alpaca replay input plan csv not found: {p.resolve()}")
    df = pd.read_csv(p)
    out: list[AlpacaReplayInputPlanRow] = []
    for _, series in df.iterrows():
        kwargs: dict[str, object] = {}
        for f in fields(AlpacaReplayInputPlanRow):
            name = f.name
            raw = series[name] if name in series.index else None
            if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                if name == "current_price":
                    kwargs[name] = None
                elif name == "has_spy_context":
                    kwargs[name] = False
                elif name in {"suggested_dte_min", "suggested_dte_max"}:
                    kwargs[name] = 0
                else:
                    kwargs[name] = ""
                continue
            if name == "has_spy_context":
                if isinstance(raw, bool):
                    kwargs[name] = raw
                else:
                    kwargs[name] = str(raw).strip().lower() in {"1", "true", "yes"}
            elif name == "current_price":
                kwargs[name] = float(raw)
            elif name in {"suggested_dte_min", "suggested_dte_max"}:
                kwargs[name] = int(raw)
            else:
                kwargs[name] = str(raw).strip()
        out.append(AlpacaReplayInputPlanRow(**kwargs))  # type: ignore[arg-type]
    return out


def load_availability_plan(
    *,
    input_csv: Path,
    candidates_csv: Path,
    spotgamma_root: Path,
    rebuild_if_missing: bool,
    dte_min: int,
    dte_max: int,
) -> tuple[list[AlpacaReplayInputPlanRow], str]:
    if input_csv.is_file():
        return load_availability_plan_from_csv(input_csv), "input_plan_csv"
    if not rebuild_if_missing:
        raise SystemExit(
            f"Input plan not found: {input_csv}. Pass --rebuild-if-missing to rebuild from candidates."
        )
    candidates, cand_source = load_replay_candidates(
        input_csv=candidates_csv,
        spotgamma_root=spotgamma_root,
        rebuild_if_missing=True,
    )
    plans = build_availability_plan(candidates, dte_min=dte_min, dte_max=dte_max)
    return plans, f"rebuilt_availability_plan|{cand_source}"


def filter_ready_for_fetch(plans: list[AlpacaReplayInputPlanRow]) -> list[AlpacaReplayInputPlanRow]:
    return [p for p in plans if p.availability_status == READY_STATUS]


def _parse_trade_date(trade_date: str) -> date:
    text = trade_date.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unsupported trade_date format: {trade_date!r}")


def expiration_window_label(trade_date: str, dte_min: int, dte_max: int) -> str:
    if dte_min < 0 or dte_max < dte_min:
        raise ValueError("invalid DTE range: require 0 <= dte_min <= dte_max")
    anchor = _parse_trade_date(trade_date)
    start = anchor + timedelta(days=dte_min)
    end = anchor + timedelta(days=dte_max)
    return f"{start.isoformat()}..{end.isoformat()}"


def strike_bounds(current_price: float, strike_buffer_pct: float) -> tuple[float, float]:
    if current_price <= 0:
        raise ValueError("current_price must be positive for strike bounds")
    if strike_buffer_pct < 0 or strike_buffer_pct > 0.5:
        raise ValueError("strike_buffer_pct must be between 0 and 0.5")
    lower = current_price * (1.0 - strike_buffer_pct)
    upper = current_price * (1.0 + strike_buffer_pct)
    return round(lower, 4), round(upper, 4)


def _group_key(plan: AlpacaReplayInputPlanRow) -> tuple[str, str]:
    return (plan.symbol.strip().upper(), plan.trade_date.strip())


def build_blueprint_request_plan(
    ready_plans: list[AlpacaReplayInputPlanRow],
    *,
    dte_min: int,
    dte_max: int,
    strike_buffer_pct: float,
    limit: int | None = None,
) -> list[AlpacaBlueprintReplayPlanRow]:
    if dte_min < 0 or dte_max < dte_min:
        raise ValueError("invalid DTE range: require 0 <= dte_min <= dte_max")
    grouped: dict[tuple[str, str], list[AlpacaReplayInputPlanRow]] = {}
    for plan in ready_plans:
        grouped.setdefault(_group_key(plan), []).append(plan)

    rows: list[AlpacaBlueprintReplayPlanRow] = []
    for (symbol, trade_date), group in sorted(grouped.items()):
        prices = [p.current_price for p in group if p.current_price is not None]
        if not prices:
            continue
        price = prices[0]
        if any(p != price for p in prices[1:]):
            price = prices[0]
        profiles = sorted({p.source_profile for p in group if p.source_profile})
        provenance_parts = sorted({p.provenance for p in group if p.provenance})
        exp_window = expiration_window_label(trade_date, dte_min, dte_max)
        lower, upper = strike_bounds(price, strike_buffer_pct)
        rows.append(
            AlpacaBlueprintReplayPlanRow(
                symbol=symbol,
                trade_date=trade_date,
                current_price=price,
                dte_min=dte_min,
                dte_max=dte_max,
                expiration_window=exp_window,
                strike_lower_bound=lower,
                strike_upper_bound=upper,
                request_reason=(
                    "spotgamma_ready|alpaca_blueprint_collect_by_expiration|"
                    f"strike_buffer_pct={strike_buffer_pct}"
                ),
                source_profile="|".join(profiles),
                has_spy_context=all(p.has_spy_context for p in group),
                provenance=f"{PROVENANCE_TAG}|upstream={'|'.join(provenance_parts)}",
                databento_next_step=DATABENTO_NEXT_STEP,
            )
        )

    if limit is not None and limit > 0:
        rows = rows[:limit]
    return rows


def blueprint_plan_to_dataframe(plans: list[AlpacaBlueprintReplayPlanRow]) -> pd.DataFrame:
    if not plans:
        return pd.DataFrame(columns=[f.name for f in fields(AlpacaBlueprintReplayPlanRow)])
    return pd.DataFrame(
        [{f.name: getattr(p, f.name) for f in fields(AlpacaBlueprintReplayPlanRow)} for p in plans]
    )


def summarize_blueprint_plan(
    ready_input_count: int,
    plans: list[AlpacaBlueprintReplayPlanRow],
) -> dict[str, object]:
    if not plans:
        return {
            "ready_for_fetch_input_count": ready_input_count,
            "request_plan_row_count": 0,
            "symbol_count": 0,
            "date_min": "",
            "date_max": "",
            "dte_min": None,
            "dte_max": None,
            "expiration_window_samples": [],
            "strike_lower_min": None,
            "strike_upper_max": None,
        }
    dates = sorted({p.trade_date for p in plans if p.trade_date})
    dte_mins = {p.dte_min for p in plans}
    dte_maxs = {p.dte_max for p in plans}
    return {
        "ready_for_fetch_input_count": ready_input_count,
        "request_plan_row_count": len(plans),
        "symbol_count": len({p.symbol for p in plans}),
        "date_min": dates[0],
        "date_max": dates[-1],
        "dte_min": min(dte_mins),
        "dte_max": max(dte_maxs),
        "expiration_window_samples": sorted({p.expiration_window for p in plans})[:5],
        "strike_lower_min": min(p.strike_lower_bound for p in plans),
        "strike_upper_max": max(p.strike_upper_bound for p in plans),
    }
