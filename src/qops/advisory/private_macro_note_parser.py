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
    r"Report\s+Date:\s*([A-Za-z]+)\s+0?(\d{1,2}),?\s*(\d{4})",
    re.IGNORECASE,
)
_WEEKDAY_DATE = re.compile(
    r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+([A-Za-z]+)\s+0?(\d{1,2}),?\s+(\d{4})",
    re.IGNORECASE,
)
_HEADER_DATE = re.compile(
    r"^[^:]+:\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+([A-Za-z]+)\s+0?(\d{1,2}),?\s+(\d{4})",
    re.IGNORECASE | re.MULTILINE,
)
_REPORT_TIME = re.compile(r"Report\s+Time:\s*(.+)", re.IGNORECASE)
_AT_TIME = re.compile(
    r"\bat\s+(\d{1,2}:\d{2}\s*(?:AM|PM)?\s*(?:ET|EST|EDT|CT|PT)?)",
    re.IGNORECASE,
)
_KEY_DATE_LINE = re.compile(
    r"[-•]\s*([A-Za-z]+)\s+0?(\d{1,2}),?\s*(\d{4})",
    re.IGNORECASE,
)
_LABELED_VALUE = re.compile(
    r"^(?P<label>[A-Za-z0-9][A-Za-z0-9 /%-]+?):\s*(?P<value>.*)$",
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

_FALSE_THEME_FRAGMENTS = frozenset(
    {
        "key dates ahead",
        "key dates",
        "upcoming dates",
    }
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


def _extract_report_date(text: str) -> str:
    for pattern in (_REPORT_DATE, _WEEKDAY_DATE, _HEADER_DATE):
        match = pattern.search(text)
        if match:
            iso = _month_to_iso(match.group(1), match.group(2), match.group(3))
            if iso:
                return iso
    return ""


def _extract_report_time(text: str) -> str:
    explicit = _first_match(_REPORT_TIME, text)
    if explicit:
        return explicit
    at_match = _AT_TIME.search(text)
    return at_match.group(1).strip() if at_match else ""


def _labeled_values(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for match in _LABELED_VALUE.finditer(text):
        label = match.group("label").strip().lower()
        if label in _FALSE_THEME_FRAGMENTS:
            continue
        value = match.group("value").strip()
        out[label] = value
    return out


def _block_after_label(text: str, label: str) -> str:
    pattern = re.compile(
        rf"^{re.escape(label)}:\s*(.*)$",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        return ""
    start = match.end()
    lines: list[str] = []
    first = match.group(1).strip()
    if first:
        lines.append(first)
    for raw in text[start:].splitlines():
        line = raw.strip()
        if not line:
            if lines:
                break
            continue
        if _LABELED_VALUE.match(line):
            break
        if line.endswith(":") and not lines:
            continue
        lines.append(line)
        if len(lines) >= 4:
            break
    return " ".join(lines).strip()


def _clean_theme(value: str) -> str:
    cleaned = value.strip().rstrip(":")
    lowered = cleaned.lower()
    if not cleaned or lowered in _FALSE_THEME_FRAGMENTS:
        return ""
    if len(cleaned) < 12 and lowered.endswith("ahead"):
        return ""
    return cleaned


def _macro_theme(text: str, labels: dict[str, str]) -> str:
    for label in ("macro theme",):
        block = _block_after_label(text, label)
        theme = _clean_theme(block or labels.get(label, ""))
        if theme:
            return theme
    return ""


def _macro_note_summary(text: str, labels: dict[str, str]) -> str:
    for label in ("macro note summary", "note summary", "market summary"):
        block = _block_after_label(text, label)
        summary = (block or labels.get(label, "")).strip()
        if summary:
            return summary
    return ""


def _level_from_labels(labels: dict[str, str], *keys: str) -> float | None:
    for key in keys:
        raw = labels.get(key.lower())
        if raw is None:
            continue
        num = parse_numeric(raw.split()[0].replace(",", ""))
        if num is not None:
            return float(num)
    return None


def _parse_confidence(
    *,
    report_date: str,
    index_levels: dict[str, float | None],
    call_wall: float | None,
    put_wall: float | None,
) -> str:
    has_levels = any(v is not None for v in index_levels.values()) or (
        call_wall is not None and put_wall is not None
    )
    if report_date and has_levels:
        return "HIGH"
    if report_date or has_levels:
        return "MEDIUM"
    return "LOW"


def parse_macro_note_text(text: str) -> dict[str, Any]:
    labels = _labeled_values(text)
    report_date = _extract_report_date(text)

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

    call_wall = _level_from_labels(labels, "call wall")
    put_wall = _level_from_labels(labels, "put wall")

    return {
        "kind": "macro_note",
        "proprietary": True,
        "private": True,
        "report_date": report_date,
        "report_time": _extract_report_time(text),
        "macro_theme": _macro_theme(text, labels),
        "key_dates": key_dates,
        "source_summary": labels.get("vendor summary", labels.get("source summary", "")),
        "index_levels": index_levels,
        "macro_note_summary": _macro_note_summary(text, labels),
        "skew_commentary": labels.get("skew commentary", ""),
        "reference_prices": ref_prices,
        "implied_1d_move_pct": implied_moves.get(1),
        "implied_5d_move_pct": implied_moves.get(5),
        "volatility_trigger": _level_from_labels(labels, "volatility trigger", "vol trigger"),
        "absolute_gamma_strike": _level_from_labels(labels, "absolute gamma strike"),
        "call_wall": call_wall,
        "put_wall": put_wall,
        "zero_gamma_level": _level_from_labels(labels, "zero gamma level", "zero gamma"),
        "gamma_tilt": labels.get("gamma tilt", ""),
        "gamma_notional": labels.get("gamma notional", ""),
        "risk_reversal_25d": risk_reversal,
        "call_volume": None if call_vol is None else float(call_vol),
        "put_volume": None if put_vol is None else float(put_vol),
        "call_open_interest": None if call_oi is None else float(call_oi),
        "put_open_interest": None if put_oi is None else float(put_oi),
        "parse_confidence": _parse_confidence(
            report_date=report_date,
            index_levels=index_levels,
            call_wall=call_wall,
            put_wall=put_wall,
        ),
    }
