"""Load SpotGamma exports by detected profile (CSV/XLSX), not legacy header assumptions."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import pandas as pd

ExportProfile = Literal["spy_history", "spy_excel", "squeeze", "vrp", "reverse_vrp"]

_SPY_EXCEL_FILENAMES = frozenset({"spy.xlsx"})

_DATE_DIR_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SPY_HISTORY_GLOB = "SPY_history*.csv"

# Normalized header (lowercase, collapsed spaces) -> canonical field name per profile.
_SPY_HISTORY_HEADERS: dict[str, str] = {
    "trade date": "trade_date",
    "previous close": "previous_close",
    "key gamma strike": "key_gamma_strike",
    "key delta strike": "key_delta_strike",
    "hedge wall": "hedge_wall",
    "call wall": "call_wall",
    "put wall": "put_wall",
    "call gamma": "call_gamma",
    "put gamma": "put_gamma",
    "call delta": "call_delta",
    "put delta": "put_delta",
    "next exp gamma": "next_exp_gamma",
    "next exp delta": "next_exp_delta",
    "top gamma exp": "top_gamma_exp",
    "top delta exp": "top_delta_exp",
    "call volume": "call_volume",
    "put volume": "put_volume",
    "next exp call vol": "next_exp_call_vol",
    "next exp put vol": "next_exp_put_vol",
    "put/call oi ratio": "put_call_oi_ratio",
    "volume ratio": "volume_ratio",
    "gamma ratio": "gamma_ratio",
    "delta ratio": "delta_ratio",
    "ne skew": "ne_skew",
    "skew": "skew",
    "1 m rv": "one_month_rv",
    "1 m iv": "one_month_iv",
    "iv rank": "iv_rank",
    "garch rank": "garch_rank",
    "skew rank": "skew_rank",
    "options implied move": "options_implied_move",
    "dpi": "dpi",
    "% dpi volume": "pct_dpi_volume",
    "5d % dpi volume": "pct_dpi_volume_5d",
}

_SQUEEZE_HEADERS: dict[str, str] = {
    "symbol": "symbol",
    "current price": "current_price",
    "stock volume": "stock_volume",
    "earnings date": "earnings_date",
    "key gamma strike": "key_gamma_strike",
    "key delta strike": "key_delta_strike",
    "hedge wall": "hedge_wall",
    "call wall": "call_wall",
    "put wall": "put_wall",
    "options impact": "options_impact",
    "next exp gamma": "next_exp_gamma",
    "next exp delta": "next_exp_delta",
    "top gamma exp": "top_gamma_exp",
    "top delta exp": "top_delta_exp",
    "put/call oi ratio": "put_call_oi_ratio",
    "volume ratio": "volume_ratio",
    "gamma ratio": "gamma_ratio",
    "delta ratio": "delta_ratio",
}

_VRP_HEADERS: dict[str, str] = {
    "symbol": "symbol",
    "current price": "current_price",
    "earnings date": "earnings_date",
    "key gamma strike": "key_gamma_strike",
    "key delta strike": "key_delta_strike",
    "hedge wall": "hedge_wall",
    "call wall": "call_wall",
    "put wall": "put_wall",
    "options impact": "options_impact",
    "ne skew": "ne_skew",
    "skew": "skew",
    "1 m rv": "one_month_rv",
    "1 m iv": "one_month_iv",
    "iv rank": "iv_rank",
    "garch rank": "garch_rank",
    "options implied move": "options_implied_move",
}

# Reverse-VRP scanner export (explicit map; same canonical fields as VRP).
_REVERSE_VRP_HEADERS: dict[str, str] = {
    **_VRP_HEADERS,
}


def normalize_header_label(name: object) -> str:
    """Strip, fix NBSP, collapse spaces, lowercase for profile matching."""
    s = str(name).replace("\xa0", " ").replace("\u00a0", " ").strip()
    s = re.sub(r"\s+", " ", s)
    return s.lower()


def _build_rename_map(columns: list[object], header_table: dict[str, str]) -> dict[str, str]:
    rename: dict[str, str] = {}
    for raw in columns:
        key = normalize_header_label(raw)
        if key in header_table:
            rename[str(raw)] = header_table[key]
    return rename


def detect_csv_profile(columns: list[object]) -> ExportProfile | None:
    keys = {normalize_header_label(c) for c in columns}
    if "trade date" in keys and "gamma ratio" in keys and "previous close" in keys:
        return "spy_history"
    return None


def is_spy_excel_filename(path: str | Path) -> bool:
    name = Path(path).name.lower()
    if name in _SPY_EXCEL_FILENAMES:
        return True
    stem = Path(path).stem.lower()
    return stem in {"spx", "spy"} or stem.endswith("_spx") or stem.endswith("_spy")


def detect_spy_excel_profile(columns: list[object]) -> bool:
    """True when columns match SPY_history / SPY.xlsx layout (not a scanner export)."""
    return detect_csv_profile(columns) == "spy_history"


def detect_xlsx_profile(columns: list[object], *, path: Path) -> ExportProfile | None:
    if is_spy_excel_filename(path) and detect_spy_excel_profile(columns):
        return "spy_excel"
    keys = {normalize_header_label(c) for c in columns}
    if "symbol" in keys and "gamma ratio" in keys and "1 m iv" not in keys and "stock volume" in keys:
        return "squeeze"
    if "symbol" in keys and "1 m iv" in keys and "iv rank" in keys:
        name = path.name.lower()
        if "reverse" in name:
            return "reverse_vrp"
        return "vrp"
    return None


def discover_raw_session_dirs(spotgamma_root: str | Path) -> list[Path]:
    raw_root = Path(spotgamma_root) / "raw"
    if not raw_root.is_dir():
        return []
    dirs = [p for p in raw_root.iterdir() if p.is_dir() and _DATE_DIR_PATTERN.match(p.name)]
    return sorted(dirs, key=lambda p: p.name)


def discover_processed_weekly_csvs(spotgamma_root: str | Path) -> list[Path]:
    proc = Path(spotgamma_root) / "processed"
    if not proc.is_dir():
        return []
    return sorted(proc.glob("spotgamma_weekly_*.csv"))


def discover_spy_history_csvs(spotgamma_root: str | Path) -> list[Path]:
    raw_root = Path(spotgamma_root) / "raw"
    if not raw_root.is_dir():
        return []
    return sorted(raw_root.rglob(_SPY_HISTORY_GLOB))


def load_processed_weekly_csv(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"processed weekly csv not found: {p.resolve()}")
    df = pd.read_csv(p)
    return df.assign(source_file=str(p.resolve()))


def _read_xlsx_with_profile(path: Path) -> tuple[pd.DataFrame, ExportProfile]:
    last_err: str | None = None
    for header_row in (0, 1):
        df = pd.read_excel(path, engine="openpyxl", header=header_row)
        profile = detect_xlsx_profile(list(df.columns), path=path)
        if profile == "spy_excel":
            last_err = f"header_row={header_row} spy excel (use load_spy_excel)"
            continue
        if profile is not None:
            if profile == "squeeze":
                table = _SQUEEZE_HEADERS
            elif profile == "reverse_vrp":
                table = _REVERSE_VRP_HEADERS
            else:
                table = _VRP_HEADERS
            rename = _build_rename_map(list(df.columns), table)
            if profile in {"vrp", "reverse_vrp"} and "symbol" not in rename.values():
                last_err = f"header_row={header_row} missing symbol map"
                continue
            if profile == "squeeze" and "symbol" not in rename.values():
                last_err = f"header_row={header_row} missing symbol map"
                continue
            out = df.rename(columns=rename)
            return out, profile
        last_err = f"header_row={header_row} unmatched columns={list(df.columns)[:6]}"
    raise ValueError(f"cannot detect xlsx profile for {path}: {last_err}")


def spy_excel_path_in_session(session_dir: str | Path) -> Path | None:
    """Return session-local SPY.xlsx if present (context file, not a scanner export)."""
    root = Path(session_dir)
    if not root.is_dir():
        return None
    for name in ("SPY.xlsx", "spy.xlsx"):
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None


def load_spy_excel(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"spy excel not found: {p.resolve()}")
    if not is_spy_excel_filename(p):
        raise ValueError(f"not a SPY excel filename: {p.name}")
    df = pd.read_excel(p, engine="openpyxl", header=0)
    if not detect_spy_excel_profile(list(df.columns)):
        raise ValueError(f"file is not spy_excel profile: {p}")
    rename = _build_rename_map(list(df.columns), _SPY_HISTORY_HEADERS)
    out = df.rename(columns=rename)
    return out.assign(source_file=str(p.resolve()), source_profile="spy_excel")


def load_spy_history_csv(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"spy history csv not found: {p.resolve()}")
    df = pd.read_csv(p)
    profile = detect_csv_profile(list(df.columns))
    if profile != "spy_history":
        raise ValueError(f"file is not spy_history profile: {p}")
    rename = _build_rename_map(list(df.columns), _SPY_HISTORY_HEADERS)
    out = df.rename(columns=rename)
    return out.assign(source_file=str(p.resolve()), source_profile="spy_history")


def load_scanner_xlsx(path: str | Path) -> tuple[pd.DataFrame, ExportProfile]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"scanner xlsx not found: {p.resolve()}")
    if is_spy_excel_filename(p):
        raise ValueError(f"SPY excel is not a scanner export: {p}")
    df, profile = _read_xlsx_with_profile(p)
    return df.assign(source_file=str(p.resolve()), source_profile=profile), profile


def session_date_from_dir(session_dir: Path) -> str | None:
    if _DATE_DIR_PATTERN.match(session_dir.name):
        return session_dir.name
    return None


def raw_input_date_from_path(path: Path) -> str | None:
    for part in path.parts:
        if _DATE_DIR_PATTERN.match(part):
            return part
    m = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
    if m:
        return m.group(1)
    return None


def parse_trade_date(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    try:
        return pd.to_datetime(s).date().isoformat()
    except (TypeError, ValueError):
        return None


def parse_numeric(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    s = str(value).strip()
    if not s or s.upper() in {"N/A", "NA", "-", "--"}:
        return None
    if s.startswith("'"):
        s = s[1:].strip()
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def parse_excel_serial_date(value: object) -> str | None:
    """Convert Excel serial numbers for date-like columns (Top Gamma Exp, etc.)."""
    num = parse_numeric(value)
    if num is None:
        return parse_trade_date(value)
    if num > 10000:
        try:
            ts = pd.Timestamp("1899-12-30") + pd.Timedelta(days=num)
            return ts.date().isoformat()
        except (OverflowError, ValueError):
            return None
    return parse_trade_date(value)


def parse_symbol(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip().upper()
    return s if s else None
