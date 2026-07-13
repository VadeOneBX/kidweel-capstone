"""Normalize vendor scanner profile loads into replay-corpus context rows."""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

import pandas as pd

from qops.ingest.spotgamma_loader import (
    discover_processed_weekly_csvs,
    discover_raw_session_dirs,
    discover_spy_history_csvs,
    load_processed_weekly_csv,
    load_scanner_xlsx,
    load_spy_excel,
    load_spy_history_csv,
    parse_excel_serial_date,
    parse_numeric,
    parse_symbol,
    parse_trade_date,
    raw_input_date_from_path,
    session_date_from_dir,
    spy_excel_path_in_session,
)

_SCANNER_FILENAMES: tuple[tuple[str, str], ...] = (
    ("squeeze.xlsx", "squeeze"),
    ("vrp.xlsx", "vrp"),
    ("reverse-vrp.xlsx", "reverse_vrp"),
)


@dataclass(frozen=True, slots=True)
class SpotGammaContextRow:
    """One replay-staging context row per ticker / session / export provenance."""

    symbol: str
    trade_date: str
    source_file: str
    source_type: str
    source_profile: str
    raw_input_date: str | None
    gamma_ratio: float | None
    vrp: float | None
    vrp_z: float | None
    iv_rank: float | None
    squeeze_score: float | None
    squeeze_state: str | None
    regime_label: str | None
    confidence: float | None
    notes: str
    missing_fields: str


def _derive_vrp(one_month_iv: float | None, one_month_rv: float | None) -> float | None:
    if one_month_iv is None or one_month_rv is None:
        return None
    return one_month_iv - one_month_rv


def _missing_list(
    *,
    gamma_ratio: float | None,
    vrp: float | None,
    iv_rank: float | None,
    squeeze_score: float | None,
    squeeze_state: str | None,
    regime_label: str | None,
    confidence: float | None,
    require_regime: bool,
    require_vrp: bool,
    require_iv_rank: bool,
) -> list[str]:
    missing: list[str] = []
    if gamma_ratio is None:
        missing.append("gamma_ratio")
    if require_vrp and vrp is None:
        missing.append("vrp")
    missing.append("vrp_z")
    if require_iv_rank and iv_rank is None:
        missing.append("iv_rank")
    if squeeze_score is None:
        missing.append("squeeze_score")
    if squeeze_state is None:
        missing.append("squeeze_state")
    if require_regime and (regime_label is None or not str(regime_label).strip()):
        missing.append("regime_label")
    if confidence is None:
        missing.append("confidence")
    return missing


def _note_parts(**kwargs: object) -> str:
    parts: list[str] = []
    for key in sorted(kwargs.keys()):
        val = kwargs[key]
        if val is None:
            continue
        if isinstance(val, float) and pd.isna(val):
            continue
        parts.append(f"{key}={val}")
    return "|".join(parts)


_SCANNER_PROFILES: frozenset[str] = frozenset({"squeeze", "vrp", "reverse_vrp"})
_SPY_MARKET_PROFILES: frozenset[str] = frozenset({"spy_history", "spy_excel"})


@dataclass(frozen=True, slots=True)
class RawSessionSpyExcelLoad:
    """Outcome of loading SPY.xlsx from one raw session folder."""

    session_date: str
    path: str | None
    context_rows: tuple[SpotGammaContextRow, ...]
    parse_error: str | None


def context_from_spy_market_row(
    row: pd.Series,
    *,
    source_profile: str,
    source_type: str,
) -> SpotGammaContextRow:
    trade_date = parse_trade_date(row.get("trade_date"))
    raw_input = raw_input_date_from_path(Path(str(row.get("source_file", ""))))
    if trade_date is None and raw_input:
        trade_date = raw_input
    gamma_ratio = parse_numeric(row.get("gamma_ratio"))
    one_month_iv = parse_numeric(row.get("one_month_iv"))
    one_month_rv = parse_numeric(row.get("one_month_rv"))
    iv_rank = parse_numeric(row.get("iv_rank"))
    vrp = _derive_vrp(one_month_iv, one_month_rv)
    regime_label = "SPY"
    notes = _note_parts(
        current_price=parse_numeric(row.get("previous_close")),
        hedge_wall=parse_numeric(row.get("hedge_wall")),
        call_wall=parse_numeric(row.get("call_wall")),
        put_wall=parse_numeric(row.get("put_wall")),
        put_call_oi_ratio=parse_numeric(row.get("put_call_oi_ratio")),
        volume_ratio=parse_numeric(row.get("volume_ratio")),
        delta_ratio=parse_numeric(row.get("delta_ratio")),
        one_month_rv=one_month_rv,
        one_month_iv=one_month_iv,
        skew=parse_numeric(row.get("skew")),
        ne_skew=parse_numeric(row.get("ne_skew")),
        top_gamma_exp=parse_excel_serial_date(row.get("top_gamma_exp")),
        top_delta_exp=parse_excel_serial_date(row.get("top_delta_exp")),
    )
    missing = _missing_list(
        gamma_ratio=gamma_ratio,
        vrp=vrp,
        iv_rank=iv_rank,
        squeeze_score=None,
        squeeze_state=None,
        regime_label=regime_label,
        confidence=None,
        require_regime=False,
        require_vrp=False,
        require_iv_rank=False,
    )
    return SpotGammaContextRow(
        symbol="SPY",
        trade_date=trade_date or "",
        source_file=str(row["source_file"]),
        source_type=source_type,
        source_profile=source_profile,
        raw_input_date=raw_input,
        gamma_ratio=gamma_ratio,
        vrp=vrp,
        vrp_z=None,
        iv_rank=iv_rank,
        squeeze_score=None,
        squeeze_state=None,
        regime_label=regime_label,
        confidence=None,
        notes=notes,
        missing_fields=",".join(missing),
    )


def context_from_spy_history_row(row: pd.Series) -> SpotGammaContextRow:
    return context_from_spy_market_row(
        row,
        source_profile="spy_history",
        source_type="SPY_HISTORY",
    )


def context_from_spy_excel_row(row: pd.Series) -> SpotGammaContextRow:
    return context_from_spy_market_row(
        row,
        source_profile="spy_excel",
        source_type="SPY_EXCEL",
    )


def load_session_spy_excel_context(session_dir: str | Path) -> RawSessionSpyExcelLoad:
    session_date = session_date_from_dir(Path(session_dir))
    if session_date is None:
        return RawSessionSpyExcelLoad(
            session_date="",
            path=None,
            context_rows=(),
            parse_error="not a dated raw session directory",
        )
    spy_path = spy_excel_path_in_session(session_dir)
    if spy_path is None:
        return RawSessionSpyExcelLoad(
            session_date=session_date,
            path=None,
            context_rows=(),
            parse_error=None,
        )
    try:
        df = load_spy_excel(spy_path)
    except (ValueError, FileNotFoundError) as exc:
        return RawSessionSpyExcelLoad(
            session_date=session_date,
            path=str(spy_path.resolve()),
            context_rows=(),
            parse_error=str(exc),
        )
    rows: list[SpotGammaContextRow] = []
    for _, series in df.iterrows():
        row = context_from_spy_excel_row(series)
        if not row.trade_date:
            continue
        rows.append(row)
    return RawSessionSpyExcelLoad(
        session_date=session_date,
        path=str(spy_path.resolve()),
        context_rows=tuple(rows),
        parse_error=None,
    )


def context_from_squeeze_row(row: pd.Series, *, session_date: str | None) -> SpotGammaContextRow:
    symbol = parse_symbol(row.get("symbol"))
    if not symbol:
        raise ValueError("squeeze row missing symbol")
    trade_date = session_date or ""
    raw_input = session_date or raw_input_date_from_path(Path(str(row["source_file"])))
    gamma_ratio = parse_numeric(row.get("gamma_ratio"))
    options_impact = parse_numeric(row.get("options_impact"))
    one_month_iv = parse_numeric(row.get("one_month_iv"))
    one_month_rv = parse_numeric(row.get("one_month_rv"))
    iv_rank = parse_numeric(row.get("iv_rank"))
    vrp = _derive_vrp(one_month_iv, one_month_rv)
    notes = _note_parts(
        current_price=parse_numeric(row.get("current_price")),
        previous_close=parse_numeric(row.get("previous_close")),
        stock_volume=parse_numeric(row.get("stock_volume")),
        hedge_wall=parse_numeric(row.get("hedge_wall")),
        call_wall=parse_numeric(row.get("call_wall")),
        put_wall=parse_numeric(row.get("put_wall")),
        key_gamma_strike=parse_numeric(row.get("key_gamma_strike")),
        key_delta_strike=parse_numeric(row.get("key_delta_strike")),
        options_impact=options_impact,
        put_call_oi_ratio=parse_numeric(row.get("put_call_oi_ratio")),
        volume_ratio=parse_numeric(row.get("volume_ratio")),
        delta_ratio=parse_numeric(row.get("delta_ratio")),
        one_month_rv=one_month_rv,
        one_month_iv=one_month_iv,
        skew=parse_numeric(row.get("skew")),
        ne_skew=parse_numeric(row.get("ne_skew")),
        garch_rank=parse_numeric(row.get("garch_rank")),
        skew_rank=parse_numeric(row.get("skew_rank")),
        options_implied_move=parse_numeric(row.get("options_implied_move")),
        top_gamma_exp=parse_excel_serial_date(row.get("top_gamma_exp")),
        top_delta_exp=parse_excel_serial_date(row.get("top_delta_exp")),
        earnings_date=parse_excel_serial_date(row.get("earnings_date")),
    )
    missing = _missing_list(
        gamma_ratio=gamma_ratio,
        vrp=vrp,
        iv_rank=iv_rank,
        squeeze_score=options_impact,
        squeeze_state=None,
        regime_label=None,
        confidence=None,
        require_regime=True,
        require_vrp=True,
        require_iv_rank=True,
    )
    return SpotGammaContextRow(
        symbol=symbol,
        trade_date=trade_date,
        source_file=str(row["source_file"]),
        source_type="SQUEEZE",
        source_profile="squeeze",
        raw_input_date=raw_input,
        gamma_ratio=gamma_ratio,
        vrp=vrp,
        vrp_z=None,
        iv_rank=iv_rank,
        squeeze_score=options_impact,
        squeeze_state=None,
        regime_label=None,
        confidence=None,
        notes=notes,
        missing_fields=",".join(missing),
    )


def context_from_vrp_row(row: pd.Series, *, profile: str, session_date: str | None) -> SpotGammaContextRow:
    symbol = parse_symbol(row.get("symbol"))
    if not symbol:
        raise ValueError(f"{profile} row missing symbol")
    trade_date = session_date or ""
    raw_input = session_date or raw_input_date_from_path(Path(str(row["source_file"])))
    one_month_iv = parse_numeric(row.get("one_month_iv"))
    one_month_rv = parse_numeric(row.get("one_month_rv"))
    iv_rank = parse_numeric(row.get("iv_rank"))
    gamma_ratio = parse_numeric(row.get("gamma_ratio"))
    vrp = _derive_vrp(one_month_iv, one_month_rv)
    source_type = "REVERSE_VRP" if profile == "reverse_vrp" else "VRP"
    notes = _note_parts(
        current_price=parse_numeric(row.get("current_price")),
        previous_close=parse_numeric(row.get("previous_close")),
        stock_volume=parse_numeric(row.get("stock_volume")),
        hedge_wall=parse_numeric(row.get("hedge_wall")),
        call_wall=parse_numeric(row.get("call_wall")),
        put_wall=parse_numeric(row.get("put_wall")),
        key_gamma_strike=parse_numeric(row.get("key_gamma_strike")),
        key_delta_strike=parse_numeric(row.get("key_delta_strike")),
        one_month_rv=one_month_rv,
        one_month_iv=one_month_iv,
        garch_rank=parse_numeric(row.get("garch_rank")),
        skew_rank=parse_numeric(row.get("skew_rank")),
        skew=parse_numeric(row.get("skew")),
        ne_skew=parse_numeric(row.get("ne_skew")),
        put_call_oi_ratio=parse_numeric(row.get("put_call_oi_ratio")),
        volume_ratio=parse_numeric(row.get("volume_ratio")),
        delta_ratio=parse_numeric(row.get("delta_ratio")),
        options_implied_move=parse_numeric(row.get("options_implied_move")),
        options_impact=parse_numeric(row.get("options_impact")),
        top_gamma_exp=parse_excel_serial_date(row.get("top_gamma_exp")),
        top_delta_exp=parse_excel_serial_date(row.get("top_delta_exp")),
        earnings_date=parse_excel_serial_date(row.get("earnings_date")),
    )
    require_regime = profile != "reverse_vrp"
    missing = _missing_list(
        gamma_ratio=gamma_ratio,
        vrp=vrp,
        iv_rank=iv_rank,
        squeeze_score=None,
        squeeze_state=None,
        regime_label=None,
        confidence=None,
        require_regime=require_regime,
        require_vrp=False,
        require_iv_rank=False,
    )
    return SpotGammaContextRow(
        symbol=symbol,
        trade_date=trade_date,
        source_file=str(row["source_file"]),
        source_type=source_type,
        source_profile=profile,
        raw_input_date=raw_input,
        gamma_ratio=gamma_ratio,
        vrp=vrp,
        vrp_z=None,
        iv_rank=iv_rank,
        squeeze_score=None,
        squeeze_state=None,
        regime_label=None,
        confidence=None,
        notes=notes,
        missing_fields=",".join(missing),
    )


def _cell_float(value: object) -> float | None:
    return parse_numeric(value)


def context_from_processed_row(row: pd.Series) -> SpotGammaContextRow:
    symbol = str(row["symbol"]).strip().upper()
    trade_date = str(row["trade_date"]).strip()
    source_file = str(row["source_file"])
    source_type = str(row["source_type"]).strip()
    gamma_ratio = _cell_float(row.get("gamma_ratio"))
    vrp = _cell_float(row.get("vrp"))
    vrp_z = _cell_float(row.get("vrp_z"))
    iv_rank = _cell_float(row.get("iv_rank"))
    regime_raw = row.get("regime_label")
    regime = None
    if regime_raw is not None and not (isinstance(regime_raw, float) and pd.isna(regime_raw)):
        s = str(regime_raw).strip()
        regime = s if s else None
    notes_raw = row.get("notes")
    notes = ""
    if notes_raw is not None and not (isinstance(notes_raw, float) and pd.isna(notes_raw)):
        notes = str(notes_raw).strip()
    conf_defaulted = "confidence:default_scalar" in notes
    confidence = None if conf_defaulted else _cell_float(row.get("confidence"))
    missing = _missing_list(
        gamma_ratio=gamma_ratio,
        vrp=vrp,
        iv_rank=iv_rank,
        squeeze_score=None,
        squeeze_state=None,
        regime_label=regime,
        confidence=confidence,
        require_regime=True,
        require_vrp=True,
        require_iv_rank=True,
    )
    return SpotGammaContextRow(
        symbol=symbol,
        trade_date=trade_date,
        source_file=source_file,
        source_type=source_type,
        source_profile="processed_weekly",
        raw_input_date=None,
        gamma_ratio=gamma_ratio,
        vrp=vrp,
        vrp_z=vrp_z,
        iv_rank=iv_rank,
        squeeze_score=None,
        squeeze_state=None,
        regime_label=regime,
        confidence=confidence,
        notes=notes,
        missing_fields=",".join(missing),
    )


def load_raw_profile_contexts(
    spotgamma_root: str | Path,
    *,
    raw_session_dates: tuple[str, ...] | None = None,
) -> list[SpotGammaContextRow]:
    root = Path(spotgamma_root)
    rows: list[SpotGammaContextRow] = []
    allowed_dates: frozenset[str] | None = None
    if raw_session_dates:
        allowed_dates = frozenset(d.strip() for d in raw_session_dates if d.strip())

    for csv_path in discover_spy_history_csvs(root):
        df = load_spy_history_csv(csv_path)
        for _, series in df.iterrows():
            row = context_from_spy_history_row(series)
            if allowed_dates is not None and row.trade_date not in allowed_dates:
                continue
            rows.append(row)

    for session_dir in discover_raw_session_dirs(root):
        session_date = session_date_from_dir(session_dir)
        if allowed_dates is not None and session_date not in allowed_dates:
            continue
        for filename, _ in _SCANNER_FILENAMES:
            path = session_dir / filename
            if not path.is_file():
                continue
            try:
                df, profile = load_scanner_xlsx(path)
            except (ValueError, FileNotFoundError):
                continue
            for _, series in df.iterrows():
                if profile == "squeeze":
                    if parse_symbol(series.get("symbol")) is None:
                        continue
                    rows.append(context_from_squeeze_row(series, session_date=session_date))
                else:
                    if parse_symbol(series.get("symbol")) is None:
                        continue
                    rows.append(context_from_vrp_row(series, profile=profile, session_date=session_date))
        spy_load = load_session_spy_excel_context(session_dir)
        rows.extend(spy_load.context_rows)
    return rows


def is_scanner_context_row(ctx: SpotGammaContextRow) -> bool:
    return ctx.source_profile in _SCANNER_PROFILES


def is_spy_market_context_row(ctx: SpotGammaContextRow) -> bool:
    return ctx.source_profile in _SPY_MARKET_PROFILES


def split_scanner_and_spy_contexts(
    contexts: list[SpotGammaContextRow],
) -> tuple[list[SpotGammaContextRow], list[SpotGammaContextRow]]:
    scanner: list[SpotGammaContextRow] = []
    spy: list[SpotGammaContextRow] = []
    for ctx in contexts:
        if is_spy_market_context_row(ctx):
            spy.append(ctx)
        elif is_scanner_context_row(ctx):
            scanner.append(ctx)
    return scanner, spy


def resolve_spy_context_source(contexts: list[SpotGammaContextRow]) -> str:
    _, spy_rows = split_scanner_and_spy_contexts(contexts)
    if not spy_rows:
        return "none"
    profiles = {r.source_profile for r in spy_rows}
    if "spy_excel" in profiles:
        return "spy_excel"
    if "spy_history" in profiles:
        return "spy_history"
    return "unknown"


def build_context_corpus(
    spotgamma_root: str | Path,
    *,
    include_raw: bool = False,
    default_confidence_for_raw: float | None = None,
    raw_session_dates: tuple[str, ...] | None = None,
    include_processed_weekly: bool = True,
) -> list[SpotGammaContextRow]:
    """Build context rows from processed weekly CSVs and optional raw profile exports."""
    _ = default_confidence_for_raw
    root = Path(spotgamma_root)
    rows: list[SpotGammaContextRow] = []
    if include_processed_weekly:
        for csv_path in discover_processed_weekly_csvs(root):
            df = load_processed_weekly_csv(csv_path)
            for _, series in df.iterrows():
                rows.append(context_from_processed_row(series))

    if include_raw:
        rows.extend(
            load_raw_profile_contexts(root, raw_session_dates=raw_session_dates)
        )
    elif raw_session_dates:
        raise ValueError("raw_session_dates requires include_raw=True")
    return rows


def contexts_to_dataframe(contexts: list[SpotGammaContextRow]) -> pd.DataFrame:
    if not contexts:
        cols = [f.name for f in fields(SpotGammaContextRow)]
        return pd.DataFrame(columns=cols)
    return pd.DataFrame([{f.name: getattr(c, f.name) for f in fields(SpotGammaContextRow)} for c in contexts])


def summarize_corpus(contexts: list[SpotGammaContextRow]) -> dict[str, str | int]:
    if not contexts:
        return {
            "row_count": 0,
            "symbol_count": 0,
            "date_min": "",
            "date_max": "",
        }
    dates = sorted({c.trade_date for c in contexts if c.trade_date})
    symbols = {c.symbol for c in contexts}
    return {
        "row_count": len(contexts),
        "symbol_count": len(symbols),
        "date_min": dates[0] if dates else "",
        "date_max": dates[-1] if dates else "",
    }


def count_by_source_profile(contexts: list[SpotGammaContextRow]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ctx in contexts:
        counts[ctx.source_profile] = counts.get(ctx.source_profile, 0) + 1
    return dict(sorted(counts.items()))


def missing_field_summary(contexts: list[SpotGammaContextRow]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ctx in contexts:
        if not ctx.missing_fields:
            continue
        for field in ctx.missing_fields.split(","):
            f = field.strip()
            if f:
                counts[f] = counts.get(f, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[0]))
