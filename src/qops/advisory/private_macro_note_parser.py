"""Parse private macro note text extracted from vendor PDFs."""

from __future__ import annotations

import re
from typing import Any

from qops.ingest.spotgamma_loader import parse_numeric

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

_REPORT_DATE = re.compile(
    r"Report\s+Date:\s*([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})",
    re.IGNORECASE,
)
_REPORT_TIME = re.compile(r"Report\s+Time:\s*(.+)", re.IGNORECASE)
_KEY_DATE_LINE = re.compile(
    r"[-•]\s*([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})",
    re.IGNORECASE,
)
_LABELED_VALUE = re.compile(
    r"^(?P<label>[A-Za-z0-9][A-Za-z0-9 /%-]+?):\s*(?P<value>.+)$",
    re.MULTILINE,
)
_RISK_REVERSAL = re.compile(
    r"25\s*[- ]?Delta\s+Risk\s+Reversal:\s*(-?[\d.]+)",
    re.IGNORECASE,
)
_PERCENT_MOVE = re.compile(
    r"Implied\s+(\d)-Day\s+Move:\s*([\d.]+%?)",
    re.IGNORECASE,
)


def _month_to_iso(month_name: str, day: str, year: str) -> str:
    month_num = _MONTHS.get(month_name.lower())
    if month_num is None:
        return ""
    return f"{year}-{month_num:02d}-{int(day):02d}"


def _parse_percent(value: str) -> float | None:
    cleaned = value.strip().rstrip("%")
    num = parse_numeric(cleaned)
    return None if num is None else float(num)


def _first_match(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _labeled_values(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for match in _LABELED_VALUE.finditer(text):
        label = match.group("label").strip().lower()
        value = match.group("value").strip()
        out[label] = value
    return out


def _level_from_labels(labels: dict[str, str], *keys: str) -> float | None:
    for key in keys:
        raw = labels.get(key.lower())
        if raw is None:
            continue
        num = parse_numeric(raw.split()[0].replace(",", ""))
        if num is not None:
            return float(num)
    return None


def parse_macro_note_text(text: str) -> dict[str, Any]:
    labels = _labeled_values(text)

    report_date = ""
    date_match = _REPORT_DATE.search(text)
    if date_match:
        report_date = _month_to_iso(date_match.group(1), date_match.group(2), date_match.group(3))

    key_dates: list[str] = []
    for match in _KEY_DATE_LINE.finditer(text):
        iso = _month_to_iso(match.group(1), match.group(2), match.group(3))
        if iso and iso not in key_dates:
            key_dates.append(iso)

    index_levels = {
        "resistance": _level_from_labels(labels, "resistance", "index resistance"),
        "pivot": _level_from_labels(labels, "pivot", "index pivot"),
        "support": _level_from_labels(labels, "support", "index support"),
    }

    implied_moves: dict[int, float | None] = {1: None, 5: None}
    for match in _PERCENT_MOVE.finditer(text):
        days = int(match.group(1))
        implied_moves[days] = _parse_percent(match.group(2))

    risk_reversal = _level_from_labels(
        labels,
        "25 delta risk reversal",
        "25-delta risk reversal",
        "risk reversal",
    )
    if risk_reversal is None:
        rr_match = _RISK_REVERSAL.search(text)
        if rr_match:
            num = parse_numeric(rr_match.group(1))
            risk_reversal = None if num is None else float(num)

    call_vol = parse_numeric(labels.get("call volume", "").replace(",", ""))
    put_vol = parse_numeric(labels.get("put volume", "").replace(",", ""))
    call_oi = parse_numeric(labels.get("call open interest", "").replace(",", ""))
    put_oi = parse_numeric(labels.get("put open interest", "").replace(",", ""))

    ref_prices: dict[str, float | None] = {}
    for sym in ("spx", "vix"):
        raw = labels.get(sym, "")
        num = parse_numeric(raw.split()[0].replace(",", "") if raw else "")
        ref_prices[sym.upper()] = None if num is None else float(num)

    return {
        "kind": "macro_note",
        "proprietary": True,
        "private": True,
        "report_date": report_date,
        "report_time": _first_match(_REPORT_TIME, text),
        "macro_theme": labels.get("macro theme", ""),
        "key_dates": key_dates,
        "source_summary": labels.get("vendor summary", labels.get("source summary", "")),
        "index_levels": index_levels,
        "macro_note_summary": labels.get("macro note summary", ""),
        "skew_commentary": labels.get("skew commentary", ""),
        "reference_prices": ref_prices,
        "implied_1d_move_pct": implied_moves.get(1),
        "implied_5d_move_pct": implied_moves.get(5),
        "volatility_trigger": _level_from_labels(labels, "volatility trigger", "vol trigger"),
        "absolute_gamma_strike": _level_from_labels(labels, "absolute gamma strike"),
        "call_wall": _level_from_labels(labels, "call wall"),
        "put_wall": _level_from_labels(labels, "put wall"),
        "zero_gamma_level": _level_from_labels(labels, "zero gamma level", "zero gamma"),
        "gamma_tilt": labels.get("gamma tilt", ""),
        "gamma_notional": labels.get("gamma notional", ""),
        "risk_reversal_25d": risk_reversal,
        "call_volume": None if call_vol is None else float(call_vol),
        "put_volume": None if put_vol is None else float(put_vol),
        "call_open_interest": None if call_oi is None else float(call_oi),
        "put_open_interest": None if put_oi is None else float(put_oi),
        "parse_confidence": "HIGH" if report_date and index_levels["resistance"] else "LOW",
    }
