"""Load SpotGamma context rows from morning staging paths (inbox → staging)."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from qops.ingest.morning_regime_upgrade import is_morning_regime_workbook_path
from qops.ingest.spotgamma_loader import (
    detect_csv_profile,
    is_spy_excel_filename,
    load_scanner_xlsx,
    load_spy_excel,
    load_spy_history_csv,
    parse_symbol,
    raw_input_date_from_path,
)
from qops.ingest.spotgamma_normalize import (
    SpotGammaContextRow,
    context_from_processed_row,
    context_from_squeeze_row,
    context_from_spy_excel_row,
    context_from_spy_history_row,
    context_from_vrp_row,
    load_raw_profile_contexts,
)

_STAGED_DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})_")


def _is_morning_regime_narrative(path: Path) -> bool:
    return is_morning_regime_workbook_path(path)


def session_date_from_staged_path(path: Path, fallback: str) -> str:
    match = _STAGED_DATE_PREFIX.match(path.name)
    if match:
        return match.group(1)
    extracted = raw_input_date_from_path(path)
    return extracted or fallback


def _load_one_staged_file(path: Path, session_date: str) -> list[SpotGammaContextRow]:
    if not path.is_file():
        raise FileNotFoundError(f"staged file not found: {path}")

    if _is_morning_regime_narrative(path):
        return []

    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(path)
        profile = detect_csv_profile(list(df.columns))
        if profile == "spy_history":
            df = load_spy_history_csv(path)
            return [context_from_spy_history_row(series) for _, series in df.iterrows()]
        df = df.assign(source_file=str(path.resolve()))
        if "source_profile" in df.columns and "symbol" in df.columns:
            return [context_from_processed_row(series) for _, series in df.iterrows()]
        raise ValueError(f"unsupported staged csv profile: {path.name}")

    if suffix in {".xlsx", ".xls"}:
        if is_spy_excel_filename(path):
            df = load_spy_excel(path)
            return [context_from_spy_excel_row(series) for _, series in df.iterrows()]

        df, profile = load_scanner_xlsx(path)
        rows: list[SpotGammaContextRow] = []
        for _, series in df.iterrows():
            if parse_symbol(series.get("symbol")) is None:
                continue
            if profile == "squeeze":
                rows.append(context_from_squeeze_row(series, session_date=session_date))
            else:
                rows.append(
                    context_from_vrp_row(series, profile=profile, session_date=session_date)
                )
        return rows

    raise ValueError(f"unsupported staged suffix: {path.suffix}")


def _merge_spy_from_raw_sessions(
    spotgamma_root: Path,
    session_dates: frozenset[str],
    existing: list[SpotGammaContextRow],
) -> list[SpotGammaContextRow]:
    if not session_dates or not spotgamma_root.is_dir():
        return existing

    have_spy_date = {
        c.trade_date
        for c in existing
        if c.source_profile in {"spy_history", "spy_excel"} and c.trade_date
    }
    extra = load_raw_profile_contexts(
        spotgamma_root,
        raw_session_dates=tuple(sorted(session_dates)),
    )
    merged = list(existing)
    for ctx in extra:
        if ctx.source_profile not in {"spy_history", "spy_excel"}:
            continue
        if ctx.trade_date and ctx.trade_date not in have_spy_date:
            merged.append(ctx)
            have_spy_date.add(ctx.trade_date)
    return merged


def load_contexts_from_staged_files(
    staged_paths: list[str],
    *,
    default_session_date: str,
    spotgamma_root: Path | None = None,
) -> list[SpotGammaContextRow]:
    """Parse/normalize staged morning exports into SpotGammaContextRow records."""
    contexts: list[SpotGammaContextRow] = []
    session_dates: set[str] = set()
    seen_paths: set[str] = set()

    for raw in staged_paths:
        path = Path(raw).resolve()
        path_key = str(path)
        if path_key in seen_paths:
            continue
        seen_paths.add(path_key)
        session_date = session_date_from_staged_path(path, default_session_date)
        session_dates.add(session_date)
        contexts.extend(_load_one_staged_file(path, session_date))

    if spotgamma_root is not None:
        contexts = _merge_spy_from_raw_sessions(
            spotgamma_root,
            frozenset(session_dates),
            contexts,
        )
    return contexts
