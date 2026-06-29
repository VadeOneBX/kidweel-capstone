"""Parse upgraded morning_regime workbooks (structured flow tabs, no OCR)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from qops.ingest.spotgamma_loader import parse_numeric, parse_symbol, parse_trade_date

_MORNING_REGIME_SHEET = "morning_regime"

UPGRADE_FLOW_SHEETS = frozenset(
    {
        "unusual_options_positions",
        "stat_sig_positions",
        "flow_candidates",
    }
)

UPGRADED_MORNING_REGIME_SHEETS = frozenset(
    {
        _MORNING_REGIME_SHEET,
        "unusual_options_positions",
        "stat_sig_positions",
        "flow_candidates",
    }
)

_PREMIUM_SUFFIX = re.compile(r"^(-?\s*[\d.,]+)\s*([MmBbKk])?\s*$")
_STAT_SIG_CELL = re.compile(
    r"^\s*[\$S]?\s*(-?[\d.,]+)\s*,\s*(\d+)\s*(?:th|st|nd|rd)?\s*$",
    re.IGNORECASE,
)

FastAdvisoryStatus = Literal["WATCH", "REVIEW", "SKIP"]


def is_morning_regime_workbook_path(path: Path) -> bool:
    stem = path.stem.lower()
    return (
        stem == "morning_regime"
        or stem.endswith("_morning_regime")
        or "morning_regime" in stem
    )


def read_sheet_names(path: Path) -> list[str]:
    """Return workbook sheet names (empty if unreadable)."""
    return discover_workbook_sheets(path)


def discover_workbook_sheets(path: Path) -> list[str]:
    if not path.is_file() or path.suffix.lower() not in {".xlsx", ".xls"}:
        return []
    try:
        xl = pd.ExcelFile(path, engine="openpyxl")
    except (OSError, ValueError):
        return []
    return list(xl.sheet_names)


def discover_upgrade_workbook_sheets(path: Path) -> list[str]:
    """Backward-compatible alias for sheet discovery."""
    return discover_workbook_sheets(path)


def is_upgraded_morning_regime_workbook(path: Path) -> bool:
    sheets = {s.strip().lower() for s in read_sheet_names(path)}
    return UPGRADED_MORNING_REGIME_SHEETS.issubset(sheets)


def is_upgrade_morning_regime_workbook(path: Path) -> bool:
    """Backward-compatible alias; authority is sheet presence, not filename."""
    return is_upgraded_morning_regime_workbook(path)


def parse_flow_premium(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    s = str(value).strip()
    if not s or s.upper() in {"N/A", "NA", "-", "--"}:
        return None
    s = s.replace(",", "").replace("$", "").strip()
    m = _PREMIUM_SUFFIX.match(s)
    if m:
        base = parse_numeric(m.group(1))
        if base is None:
            return None
        suffix = (m.group(2) or "").upper()
        mult = {"M": 1_000_000, "B": 1_000_000_000, "K": 1_000}.get(suffix, 1)
        return float(base) * mult
    return parse_numeric(s)


def normalize_option_type(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip().upper()
    if not s:
        return None
    if s in {"C", "CALL", "CALLS"}:
        return "C"
    if s in {"P", "PUT", "PUTS"}:
        return "P"
    return s[:1] if s[:1] in {"C", "P"} else None


def normalize_spread_id(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    if not s:
        return None
    return re.sub(r"\s+", " ", s)


def normalize_spread_id_family(spread_id: str | None) -> str:
    if not spread_id:
        return ""
    family = spread_id.lower()
    for token in (" open", " close", " roll"):
        if family.endswith(token):
            family = family[: -len(token)]
    return family.strip()


@dataclass(frozen=True, slots=True)
class UnusualOptionsRow:
    symbol: str
    expiration: str
    strike: float
    option_type: str | None
    total_volume: float | None
    bto: float | None
    btc: float | None
    sto: float | None
    stc: float | None
    buy_premium: float | None
    sell_premium: float | None
    total_premium: float | None
    spread_id: str | None
    source_sheet: str
    source_workbook: str


@dataclass(frozen=True, slots=True)
class StatSigRow:
    symbol: str
    sector: str
    delta_mm: float | None
    delta_percentile: int | None
    gamma_mm: float | None
    gamma_percentile: int | None
    vega_mm: float | None
    vega_percentile: int | None
    delta_raw: str = ""
    gamma_raw: str = ""
    vega_raw: str = ""
    source_sheet: str = "stat_sig_positions"
    source_workbook: str = ""


@dataclass(frozen=True, slots=True)
class FlowCandidateRow:
    symbol: str
    expiration: str
    strike: float
    option_type: str | None
    spread_id: str | None
    source_sheet: str = "flow_candidates"
    source_workbook: str = ""


@dataclass(frozen=True, slots=True)
class FastAdvisoryCandidate:
    candidate_detected: bool
    symbol: str
    expiration: str
    structure_family: str
    structure_type_hint: str
    strikes: tuple[float, ...]
    spread_id: str | None
    long_leg_strike: float | None
    short_leg_strike: float | None
    supporting_unusual_flow: bool
    fast_advisory_status: FastAdvisoryStatus
    paper_submission_status: str
    source_sheet: str
    source_workbook: str


@dataclass(frozen=True, slots=True)
class MorningRegimeUpgradeIntake:
    workbook: str
    workbook_path: str
    sheets_found: list[str]
    morning_regime_narrative_lines: int
    unusual_rows: tuple[UnusualOptionsRow, ...]
    stat_sig_rows: tuple[StatSigRow, ...]
    flow_candidate_rows: tuple[FlowCandidateRow, ...]
    fast_advisory_candidates: tuple[FastAdvisoryCandidate, ...]
    image_ocr_used: bool = False
    embedded_image_count: int = 0


def parse_stat_sig_greek_cell(value: object) -> tuple[float | None, int | None, str]:
    raw = "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value).strip()
    if not raw:
        return None, None, raw
    m = _STAT_SIG_CELL.match(raw.replace("$", "").replace("S", "", 1) if raw.startswith("S") else raw)
    if not m:
        cleaned = raw.replace("$", "").replace("S", "").strip()
        m = _STAT_SIG_CELL.match(cleaned)
    if not m:
        return None, None, raw
    mm = parse_numeric(m.group(1))
    pct = int(m.group(2))
    return mm, pct, raw


def _row_is_blank(series: pd.Series) -> bool:
    for v in series:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            continue
        if str(v).strip():
            return False
    return True


def _read_sheet_df(path: Path, sheet_name: str) -> pd.DataFrame | None:
    try:
        df = pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl", header=0)
    except (OSError, ValueError, KeyError):
        return None
    if df.empty:
        return df
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _col(series: pd.Series, *names: str) -> object:
    cols = {str(c).strip().lower(): c for c in series.index}
    for name in names:
        key = name.lower()
        if key in cols:
            return series.get(cols[key])
    return None


def parse_unusual_options_positions(
    path: Path,
    *,
    sheet_name: str = "unusual_options_positions",
) -> list[UnusualOptionsRow]:
    df = _read_sheet_df(path, sheet_name)
    if df is None or df.empty:
        return []
    workbook_name = path.name
    rows: list[UnusualOptionsRow] = []
    for _, series in df.iterrows():
        if _row_is_blank(series):
            continue
        symbol = parse_symbol(_col(series, "Stock", "Symbol"))
        if not symbol:
            continue
        expiration = parse_trade_date(_col(series, "Exp", "Expiration"))
        if not expiration:
            continue
        strike = parse_numeric(_col(series, "Strike"))
        if strike is None:
            continue
        rows.append(
            UnusualOptionsRow(
                symbol=symbol,
                expiration=expiration,
                strike=float(strike),
                option_type=normalize_option_type(_col(series, "Type")),
                total_volume=parse_numeric(_col(series, "Tot Vol", "Total Volume")),
                bto=parse_numeric(_col(series, "BTO")),
                btc=parse_numeric(_col(series, "BTC")),
                sto=parse_numeric(_col(series, "STO")),
                stc=parse_numeric(_col(series, "STC")),
                buy_premium=parse_flow_premium(_col(series, "Buy Prem", "Buy Premium")),
                sell_premium=parse_flow_premium(_col(series, "Sell Prem", "Sell Premium")),
                total_premium=parse_flow_premium(_col(series, "Total Prem", "Total Premium")),
                spread_id=normalize_spread_id(_col(series, "Spread ID", "SpreadID")),
                source_sheet=sheet_name,
                source_workbook=workbook_name,
            )
        )
    return rows


def parse_stat_sig_positions(
    path: Path,
    *,
    sheet_name: str = "stat_sig_positions",
) -> list[StatSigRow]:
    df = _read_sheet_df(path, sheet_name)
    if df is None or df.empty:
        return []
    workbook_name = path.name
    rows: list[StatSigRow] = []
    for _, series in df.iterrows():
        if _row_is_blank(series):
            continue
        symbol = parse_symbol(_col(series, "Symbol", "Stock"))
        if not symbol:
            continue
        sector = str(_col(series, "Sector") or "").strip()
        d_mm, d_pct, d_raw = parse_stat_sig_greek_cell(_col(series, "Delta ($M,%'ile)", "Delta"))
        g_mm, g_pct, g_raw = parse_stat_sig_greek_cell(_col(series, "Gamma ($M,%'ile)", "Gamma"))
        v_mm, v_pct, v_raw = parse_stat_sig_greek_cell(_col(series, "Vega (SM,%'ile)", "Vega"))
        rows.append(
            StatSigRow(
                symbol=symbol,
                sector=sector,
                delta_mm=d_mm,
                delta_percentile=d_pct,
                gamma_mm=g_mm,
                gamma_percentile=g_pct,
                vega_mm=v_mm,
                vega_percentile=v_pct,
                delta_raw=d_raw,
                gamma_raw=g_raw,
                vega_raw=v_raw,
                source_sheet=sheet_name,
                source_workbook=workbook_name,
            )
        )
    return rows


def parse_flow_candidates(
    path: Path,
    *,
    sheet_name: str = "flow_candidates",
) -> list[FlowCandidateRow]:
    df = _read_sheet_df(path, sheet_name)
    if df is None or df.empty:
        return []
    workbook_name = path.name
    rows: list[FlowCandidateRow] = []
    for _, series in df.iterrows():
        if _row_is_blank(series):
            continue
        symbol = parse_symbol(_col(series, "Stock", "Symbol"))
        if not symbol:
            continue
        expiration = parse_trade_date(_col(series, "Exp", "Expiration"))
        if not expiration:
            continue
        strike = parse_numeric(_col(series, "Strike"))
        if strike is None:
            continue
        rows.append(
            FlowCandidateRow(
                symbol=symbol,
                expiration=expiration,
                strike=float(strike),
                option_type=normalize_option_type(_col(series, "Type")),
                spread_id=normalize_spread_id(_col(series, "Spread ID", "SpreadID")),
                source_sheet=sheet_name,
                source_workbook=workbook_name,
            )
        )
    return rows


def _count_embedded_images(path: Path) -> int:
    try:
        from openpyxl import load_workbook
    except ImportError:
        return 0
    try:
        wb = load_workbook(path, read_only=True, data_only=True)
    except (OSError, ValueError):
        return 0
    count = 0
    for ws in wb.worksheets:
        images = getattr(ws, "_images", None)
        if images:
            count += len(images)
    wb.close()
    return count


def _morning_regime_narrative_line_count(path: Path) -> int:
    try:
        df = pd.read_excel(
            path,
            sheet_name=_MORNING_REGIME_SHEET,
            engine="openpyxl",
            header=None,
        )
    except (OSError, ValueError, KeyError):
        return 0
    lines = 0
    for val in df.iloc[:, 0] if not df.empty else []:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            continue
        if str(val).strip():
            lines += 1
    return lines


def _structure_family_from_spread_id(spread_id: str | None) -> tuple[str, str]:
    sid = (spread_id or "").lower()
    if "call spread" in sid:
        return "call_spread", "BULL_CALL_SPREAD"
    if "put spread" in sid:
        return "put_spread", "BEAR_PUT_SPREAD"
    if "put roll" in sid:
        return "put_roll", "SKIP"
    return "unknown_spread", "SKIP"


def _unusual_supports_spread(
    unusual_rows: tuple[UnusualOptionsRow, ...],
    *,
    symbol: str,
    expiration: str,
    strikes: tuple[float, ...],
    spread_family: str,
) -> bool:
    strike_set = {round(s, 4) for s in strikes}
    for row in unusual_rows:
        if row.symbol != symbol or row.expiration != expiration:
            continue
        if round(row.strike, 4) not in strike_set:
            continue
        row_family = normalize_spread_id_family(row.spread_id)
        if spread_family and row_family and spread_family not in row_family:
            continue
        return True
    return False


def extract_fast_advisory_candidates(
    flow_rows: list[FlowCandidateRow] | tuple[FlowCandidateRow, ...],
    unusual_rows: list[UnusualOptionsRow] | tuple[UnusualOptionsRow, ...],
    *,
    source_workbook: str,
) -> list[FastAdvisoryCandidate]:
    grouped: dict[tuple[str, str, str, str], list[FlowCandidateRow]] = {}
    for row in flow_rows:
        opt = row.option_type or ""
        family = normalize_spread_id_family(row.spread_id)
        key = (row.symbol, row.expiration, opt, family)
        grouped.setdefault(key, []).append(row)

    candidates: list[FastAdvisoryCandidate] = []
    for (symbol, expiration, opt_type, family), legs in grouped.items():
        if len(legs) < 2:
            continue
        strikes = tuple(sorted({leg.strike for leg in legs}))
        if len(strikes) < 2:
            continue
        spread_id = legs[0].spread_id
        structure_family, structure_hint = _structure_family_from_spread_id(spread_id)
        if structure_family == "unknown_spread":
            continue

        unusual_tuple = tuple(unusual_rows)
        supporting = _unusual_supports_spread(
            unusual_tuple,
            symbol=symbol,
            expiration=expiration,
            strikes=strikes,
            spread_family=family,
        )

        long_strike: float | None = None
        short_strike: float | None = None
        if structure_family == "call_spread":
            long_strike = max(strikes)
            short_strike = min(strikes)
        elif structure_family == "put_spread":
            long_strike = max(strikes)
            short_strike = min(strikes)

        status: FastAdvisoryStatus = "WATCH" if supporting else "REVIEW"
        candidates.append(
            FastAdvisoryCandidate(
                candidate_detected=True,
                symbol=symbol,
                expiration=expiration,
                structure_family=structure_family,
                structure_type_hint=structure_hint,
                strikes=strikes,
                spread_id=spread_id,
                long_leg_strike=long_strike,
                short_leg_strike=short_strike,
                supporting_unusual_flow=supporting,
                fast_advisory_status=status,
                paper_submission_status="gated_not_submitted",
                source_sheet="flow_candidates",
                source_workbook=source_workbook,
            )
        )
    return candidates


def load_morning_regime_upgrade(path: str | Path) -> MorningRegimeUpgradeIntake:
    p = Path(path).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"morning regime workbook not found: {p}")

    sheets = discover_workbook_sheets(p)
    sheets_lower = {s.lower() for s in sheets}

    unusual: list[UnusualOptionsRow] = []
    if "unusual_options_positions" in sheets_lower:
        sheet = next(s for s in sheets if s.lower() == "unusual_options_positions")
        unusual = parse_unusual_options_positions(p, sheet_name=sheet)

    stat_sig: list[StatSigRow] = []
    if "stat_sig_positions" in sheets_lower:
        sheet = next(s for s in sheets if s.lower() == "stat_sig_positions")
        stat_sig = parse_stat_sig_positions(p, sheet_name=sheet)

    flow: list[FlowCandidateRow] = []
    if "flow_candidates" in sheets_lower:
        sheet = next(s for s in sheets if s.lower() == "flow_candidates")
        flow = parse_flow_candidates(p, sheet_name=sheet)

    fast = extract_fast_advisory_candidates(
        flow,
        unusual,
        source_workbook=p.name,
    )

    return MorningRegimeUpgradeIntake(
        workbook=p.name,
        workbook_path=str(p),
        sheets_found=sheets,
        morning_regime_narrative_lines=_morning_regime_narrative_line_count(p),
        unusual_rows=tuple(unusual),
        stat_sig_rows=tuple(stat_sig),
        flow_candidate_rows=tuple(flow),
        fast_advisory_candidates=tuple(fast),
        image_ocr_used=False,
        embedded_image_count=_count_embedded_images(p),
    )


def intake_to_audit_dict(intake: MorningRegimeUpgradeIntake) -> dict[str, object]:
    workbook_format = (
        "upgraded"
        if UPGRADED_MORNING_REGIME_SHEETS.issubset(
            {s.strip().lower() for s in intake.sheets_found}
        )
        else "legacy"
    )
    return {
        "workbook": intake.workbook,
        "workbook_format": workbook_format,
        "workbook_path": intake.workbook_path,
        "sheets_found": intake.sheets_found,
        "morning_regime_narrative_lines": intake.morning_regime_narrative_lines,
        "unusual_rows_parsed": len(intake.unusual_rows),
        "stat_sig_rows_parsed": len(intake.stat_sig_rows),
        "flow_candidates_parsed": len(intake.flow_candidate_rows),
        "fast_advisory_candidates": [
            {
                "candidate_detected": c.candidate_detected,
                "symbol": c.symbol,
                "expiration": c.expiration,
                "structure_family": c.structure_family,
                "structure_type_hint": c.structure_type_hint,
                "strikes": list(c.strikes),
                "spread_id": c.spread_id,
                "supporting_unusual_flow": c.supporting_unusual_flow,
                "status": c.fast_advisory_status,
                "fast_advisory_status": c.fast_advisory_status,
                "paper_submission_status": c.paper_submission_status,
                "source_sheet": c.source_sheet,
            }
            for c in intake.fast_advisory_candidates
        ],
        "image_ocr_used": intake.image_ocr_used,
        "embedded_image_count": intake.embedded_image_count,
    }


def write_morning_regime_intake_audit(
    base_dir: Path,
    intake: MorningRegimeUpgradeIntake,
    *,
    audit_filename: str = "morning_regime_latest.json",
    write_compat_upgrade_audit: bool = True,
) -> Path:
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    payload = intake_to_audit_dict(intake)
    out_path = logs_dir / audit_filename
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if write_compat_upgrade_audit and audit_filename != "morning_regime_upgrade_latest.json":
        compat = logs_dir / "morning_regime_upgrade_latest.json"
        compat.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path


def write_upgrade_intake_audit(
    base_dir: Path,
    intake: MorningRegimeUpgradeIntake,
    *,
    audit_filename: str = "morning_regime_latest.json",
) -> Path:
    """Backward-compatible alias."""
    return write_morning_regime_intake_audit(
        base_dir,
        intake,
        audit_filename=audit_filename,
    )


def run_morning_regime_intake(
    base_dir: Path,
    workbook_path: str | Path,
) -> tuple[MorningRegimeUpgradeIntake, Path]:
    intake = load_morning_regime_upgrade(workbook_path)
    audit_path = write_morning_regime_intake_audit(base_dir, intake)
    return intake, audit_path


def run_morning_regime_upgrade_intake(
    base_dir: Path,
    workbook_path: str | Path,
) -> tuple[MorningRegimeUpgradeIntake, Path]:
    """Backward-compatible alias."""
    return run_morning_regime_intake(base_dir, workbook_path)


def discover_upgraded_morning_regime_workbooks(
    base_dir: Path,
    *,
    run_date: str,
    staged_files: list[str] | None = None,
) -> list[Path]:
    from qops.advisory.am_note_gate import discover_morning_regime_paths

    paths = discover_morning_regime_paths(
        base_dir,
        run_date=run_date,
        staged_files=staged_files,
    )
    upgraded = [p for p in paths if is_upgraded_morning_regime_workbook(p)]
    if upgraded:
        return upgraded
    if staged_files:
        for raw in staged_files:
            p = Path(raw)
            if p.is_file() and is_upgraded_morning_regime_workbook(p):
                return [p.resolve()]
    return []


def discover_upgrade_workbooks(
    base_dir: Path,
    *,
    run_date: str,
    staged_files: list[str] | None = None,
) -> list[Path]:
    """Backward-compatible alias."""
    return discover_upgraded_morning_regime_workbooks(
        base_dir,
        run_date=run_date,
        staged_files=staged_files,
    )


def fast_advisory_candidate_to_dict(candidate: FastAdvisoryCandidate) -> dict[str, object]:
    return asdict(candidate)
