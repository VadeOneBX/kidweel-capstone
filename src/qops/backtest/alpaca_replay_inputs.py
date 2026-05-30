"""Plan Alpaca historical replay data needs for SpotGamma candidates (no fetch, no orders)."""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

import pandas as pd

from qops.backtest.spotgamma_replay_builder import ReplayCandidateRow, build_replay_candidates
from qops.ingest.spotgamma_loader import parse_numeric
from qops.ingest.spotgamma_normalize import build_context_corpus

DEFAULT_ENTRY_WINDOW = "09:45-15:00 ET (skip first 30m, last 60m)"
PROVENANCE_TAG = "sg_bt_c3_availability_plan"


@dataclass(frozen=True, slots=True)
class AlpacaReplayInputPlanRow:
    symbol: str
    trade_date: str
    source_profile: str
    current_price: float | None
    has_spy_context: bool
    required_underlying_bars: str
    required_option_chain: str
    required_option_bars: str
    suggested_dte_min: int
    suggested_dte_max: int
    suggested_entry_window: str
    availability_status: str
    missing_requirements: str
    provenance: str


def load_replay_candidates_from_csv(path: str | Path) -> list[ReplayCandidateRow]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"replay candidates csv not found: {p.resolve()}")
    df = pd.read_csv(p)
    float_fields = {
        f.name
        for f in fields(ReplayCandidateRow)
        if f.name
        not in {
            "symbol",
            "trade_date",
            "source_profile",
            "source_file",
            "candidate_reason",
            "missing_fields",
            "has_spy_context",
        }
    }
    out: list[ReplayCandidateRow] = []
    for _, series in df.iterrows():
        kwargs: dict[str, object] = {}
        for f in fields(ReplayCandidateRow):
            name = f.name
            raw = series[name] if name in series.index else None
            if name == "has_spy_context":
                if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                    kwargs[name] = False
                elif isinstance(raw, bool):
                    kwargs[name] = raw
                else:
                    kwargs[name] = str(raw).strip().lower() in {"1", "true", "yes"}
                continue
            if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                kwargs[name] = None if name in float_fields else ""
                continue
            if name in float_fields:
                kwargs[name] = parse_numeric(raw)
            else:
                kwargs[name] = str(raw).strip()
        out.append(ReplayCandidateRow(**kwargs))  # type: ignore[arg-type]
    return out


def rebuild_replay_candidates(spotgamma_root: str | Path) -> list[ReplayCandidateRow]:
    """Rebuild candidates from fresh SpotGamma context (ingest include_raw)."""
    contexts = build_context_corpus(spotgamma_root, include_raw=True)
    return build_replay_candidates(contexts)


def load_replay_candidates(
    *,
    input_csv: Path,
    spotgamma_root: Path,
    rebuild_if_missing: bool,
) -> tuple[list[ReplayCandidateRow], str]:
    if input_csv.is_file():
        return load_replay_candidates_from_csv(input_csv), "candidate_csv"
    if rebuild_if_missing:
        return rebuild_replay_candidates(spotgamma_root), "rebuilt_from_ingest"
    raise SystemExit(
        f"Candidate input not found: {input_csv}. Pass --rebuild-if-missing to rebuild from ingest."
    )


def _required_underlying_bars(symbol: str, trade_date: str, entry_window: str) -> str:
    return (
        f"read-only underlying bars: symbol={symbol} date={trade_date} "
        f"session_window={entry_window}"
    )


def _required_option_chain(symbol: str, trade_date: str, dte_min: int, dte_max: int) -> str:
    return (
        f"read-only option chain snapshot: underlying={symbol} as_of={trade_date} "
        f"expirations_dte={dte_min}-{dte_max} (no strike selection)"
    )


def _required_option_bars(symbol: str, trade_date: str, dte_min: int, dte_max: int, entry_window: str) -> str:
    return (
        f"read-only option bars: underlying={symbol} date={trade_date} "
        f"dte={dte_min}-{dte_max} window={entry_window} contracts=TBD"
    )


def build_availability_plan_row(
    candidate: ReplayCandidateRow,
    *,
    dte_min: int,
    dte_max: int,
    entry_window: str = DEFAULT_ENTRY_WINDOW,
) -> AlpacaReplayInputPlanRow:
    missing: list[str] = []
    symbol = (candidate.symbol or "").strip().upper()
    trade_date = (candidate.trade_date or "").strip()

    if not symbol:
        missing.append("symbol")
    if not trade_date:
        missing.append("trade_date")
    if candidate.current_price is None:
        missing.append("current_price")
    if not candidate.has_spy_context:
        missing.append("spy_market_context")

    if not symbol:
        status = "MISSING_SYMBOL"
    elif not trade_date:
        status = "MISSING_TRADE_DATE"
    elif candidate.current_price is None:
        status = "MISSING_PRICE"
    elif not candidate.has_spy_context:
        status = "MISSING_CONTEXT"
    else:
        status = "READY_FOR_FETCH"

    provenance = f"{PROVENANCE_TAG}|candidate_source={candidate.source_file}"

    return AlpacaReplayInputPlanRow(
        symbol=symbol,
        trade_date=trade_date,
        source_profile=candidate.source_profile,
        current_price=candidate.current_price,
        has_spy_context=candidate.has_spy_context,
        required_underlying_bars=_required_underlying_bars(symbol or "?", trade_date or "?", entry_window),
        required_option_chain=_required_option_chain(symbol or "?", trade_date or "?", dte_min, dte_max),
        required_option_bars=_required_option_bars(symbol or "?", trade_date or "?", dte_min, dte_max, entry_window),
        suggested_dte_min=dte_min,
        suggested_dte_max=dte_max,
        suggested_entry_window=entry_window,
        availability_status=status,
        missing_requirements=",".join(missing),
        provenance=provenance,
    )


def build_availability_plan(
    candidates: list[ReplayCandidateRow],
    *,
    dte_min: int = 0,
    dte_max: int = 7,
    entry_window: str = DEFAULT_ENTRY_WINDOW,
) -> list[AlpacaReplayInputPlanRow]:
    if dte_min < 0 or dte_max < dte_min:
        raise ValueError("invalid DTE range: require 0 <= dte_min <= dte_max")
    return [
        build_availability_plan_row(c, dte_min=dte_min, dte_max=dte_max, entry_window=entry_window)
        for c in candidates
    ]


def plan_to_dataframe(plans: list[AlpacaReplayInputPlanRow]) -> pd.DataFrame:
    if not plans:
        return pd.DataFrame(columns=[f.name for f in fields(AlpacaReplayInputPlanRow)])
    return pd.DataFrame([{f.name: getattr(p, f.name) for f in fields(AlpacaReplayInputPlanRow)} for p in plans])


def summarize_availability_plan(plans: list[AlpacaReplayInputPlanRow]) -> dict[str, object]:
    if not plans:
        return {
            "plan_row_count": 0,
            "symbol_count": 0,
            "date_min": "",
            "date_max": "",
            "ready_for_fetch": 0,
            "by_status": {},
            "missing_requirements_summary": {},
        }
    dates = sorted({p.trade_date for p in plans if p.trade_date})
    by_status: dict[str, int] = {}
    miss_counts: dict[str, int] = {}
    for p in plans:
        by_status[p.availability_status] = by_status.get(p.availability_status, 0) + 1
        for part in p.missing_requirements.split(","):
            key = part.strip()
            if key:
                miss_counts[key] = miss_counts.get(key, 0) + 1
    return {
        "plan_row_count": len(plans),
        "symbol_count": len({p.symbol for p in plans if p.symbol}),
        "date_min": dates[0] if dates else "",
        "date_max": dates[-1] if dates else "",
        "ready_for_fetch": by_status.get("READY_FOR_FETCH", 0),
        "by_status": dict(sorted(by_status.items())),
        "missing_requirements_summary": dict(
            sorted(miss_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ),
    }


def fetch_historical_data_read_only() -> None:
    """Placeholder: historical Alpaca read-only fetch is a future packet (not C3)."""
    raise NotImplementedError(
        "Alpaca historical fetch is not implemented in SG-BT-C3. "
        "This packet produces an availability plan only."
    )
