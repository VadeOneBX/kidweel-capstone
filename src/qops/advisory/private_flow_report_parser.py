"""Parse private flow report text extracted from vendor PDFs."""

from __future__ import annotations

import re
from typing import Any

from qops.ingest.spotgamma_loader import parse_numeric, parse_symbol

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
_NOTABLE_ROW = re.compile(
    r"^([A-Z][A-Z0-9.]{0,5})\s+([A-Za-z][A-Za-z\s/&-]+?)\s+\$?\s*([\d.,]+)\s*M?,?\s*(\d+)(?:st|nd|rd|th)?\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_SECTOR_STAT = re.compile(
    r"^([A-Za-z][A-Za-z\s/&-]+?)\s+avg\s+delta\s+percentile\s+(\d+)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_URL_LINE = re.compile(r"https?://\S+", re.IGNORECASE)
_PAGE_FOOTER = re.compile(r"^\s*\d+\s*(?:/\s*\d+)?\s*$")
_BOILERPLATE_LINE = re.compile(
    r"^\s*(?:©|copyright|all rights reserved|confidential|proprietary)\b.*$",
    re.IGNORECASE,
)

# Canonical section keys map to one or more header strings seen in vendor PDF extracts.
_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "overview": ("Overview", "Executive Summary"),
    "index_positioning": ("Index Positioning Summary", "Index ETF Positioning Summary"),
    "stock_positioning": ("Stock Positioning Summary", "Single Stock Positioning Summary"),
    "sector_mix": ("Sector Mix", "Sector Breakdown"),
    "directional": ("Directional Table", "Directional Positioning"),
    "gamma": ("Gamma Table", "Gamma Positioning"),
    "volatility": ("Volatility Table", "Volatility Positioning"),
    "large_trades": ("Large Trades", "Largest Premium Trades"),
    "index_trades": ("Index Trades", "Largest Index Trades"),
    "unusual": ("Unusual Positions", "Unusual Options Positions"),
    "notable": ("Notable Positions", "Statistically Significant Positions"),
    "sector_stats": ("Sector Stats", "Sector Statistical Analysis"),
    "algo": ("Algo Flow", "Heavy Daytrading/Algo Flow", "Heavy Daytrading/ Algo Flow"),
}

_ALL_HEADERS: tuple[str, ...] = tuple(
    header for aliases in _SECTION_ALIASES.values() for header in aliases
)


def _month_to_iso(month_name: str, day: str, year: str) -> str:
    month_num = _MONTHS.get(month_name.lower())
    if month_num is None:
        return ""
    return f"{year}-{month_num:02d}-{int(day):02d}"


def _extract_report_date(text: str) -> str:
    for pattern in (_REPORT_DATE, _WEEKDAY_DATE, _HEADER_DATE):
        match = pattern.search(text)
        if match:
            iso = _month_to_iso(match.group(1), match.group(2), match.group(3))
            if iso:
                return iso
    return ""


def _preprocess_flow_text(text: str) -> str:
    lines: list[str] = []
    for raw in text.splitlines():
        line = _URL_LINE.sub("", raw).strip()
        if not line:
            continue
        if _PAGE_FOOTER.match(line):
            continue
        if _BOILERPLATE_LINE.match(line):
            continue
        lines.append(line)
    return "\n".join(lines)


def _section_text(text: str, section_key: str) -> str:
    aliases = _SECTION_ALIASES.get(section_key, ())
    for header in aliases:
        start = text.lower().find(header.lower())
        if start < 0:
            continue
        start += len(header)
        end = len(text)
        lowered = text.lower()
        for other in _ALL_HEADERS:
            if other.lower() == header.lower():
                continue
            idx = lowered.find(other.lower(), start)
            if idx >= 0:
                end = min(end, idx)
        block = text[start:end].strip()
        if block:
            return block
    return ""


def _parse_bullets(block: str) -> list[str]:
    bullets: list[str] = []
    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(("-", "•", "*", "●")):
            bullets.append(line.lstrip("-•*● ").strip())
        elif not bullets and line and not _LABELED_LINE(line):
            bullets.append(line)
    return bullets


def _LABELED_LINE(line: str) -> bool:
    return bool(re.match(r"^[A-Za-z][A-Za-z0-9 /%-]+:\s*\S", line))


def _parse_positioning_table(block: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    if len(lines) < 2:
        return rows
    for line in lines[1:]:
        parts = re.split(r"\s{2,}|\t", line)
        if len(parts) < 2:
            parts = line.split()
        if len(parts) < 2:
            continue
        symbol = parse_symbol(parts[0])
        if not symbol:
            continue
        delta_mm = parse_numeric(parts[1].replace("$", "").replace(",", ""))
        percentile = parse_numeric(parts[2]) if len(parts) > 2 else None
        rows.append(
            {
                "symbol": symbol,
                "delta_mm": None if delta_mm is None else float(delta_mm),
                "percentile": None if percentile is None else int(percentile),
            }
        )
    return rows


def _parse_sector_breakdown(block: str) -> list[dict[str, object]]:
    sectors: list[dict[str, object]] = []
    for line in block.splitlines():
        line = line.strip()
        if not line or "%" not in line:
            continue
        match = re.match(r"^([A-Za-z][A-Za-z\s/&-]+?)\s+([\d.]+)%\s*$", line)
        if match:
            sectors.append(
                {
                    "sector": match.group(1).strip(),
                    "weight_pct": float(match.group(2)),
                }
            )
    return sectors


def _parse_trade_lines(block: str) -> list[str]:
    return [ln.strip() for ln in block.splitlines() if ln.strip()]


def _parse_notable_rows(text: str) -> list[dict[str, object]]:
    notable_block = _section_text(text, "notable")
    search_text = notable_block or text
    rows: list[dict[str, object]] = []
    for match in _NOTABLE_ROW.finditer(search_text):
        symbol = parse_symbol(match.group(1))
        if not symbol:
            continue
        delta_raw = match.group(3).replace(",", "")
        delta_mm = parse_numeric(delta_raw)
        if delta_mm is None:
            continue
        rows.append(
            {
                "symbol": symbol,
                "sector": match.group(2).strip(),
                "delta_mm": float(delta_mm),
                "delta_percentile": int(match.group(4)),
            }
        )
    return rows


def _symbol_from_trade_line(line: str) -> str | None:
    token = line.strip().split()[0] if line.strip() else ""
    return parse_symbol(token)


def _derive_top_symbols(
    notable_rows: list[dict[str, object]],
    directional_table: list[dict[str, object]],
    large_trades: list[str],
    unusual_positions: list[str],
) -> list[str]:
    ordered: list[str] = []
    for row in notable_rows:
        sym = str(row.get("symbol", "")).strip().upper()
        if sym and sym not in ordered:
            ordered.append(sym)
    for row in directional_table:
        sym = str(row.get("symbol", "")).strip().upper()
        if sym and sym not in ordered:
            ordered.append(sym)
    for line in large_trades + unusual_positions:
        sym = _symbol_from_trade_line(line)
        if sym and sym not in ordered:
            ordered.append(sym)
    return ordered[:10]


def _parse_confidence(
    *,
    report_date: str,
    overview_bullets: list[str],
    notable_rows: list[dict[str, object]],
    top_symbols: list[str],
) -> str:
    has_flow = bool(overview_bullets or notable_rows or top_symbols)
    if report_date and has_flow:
        return "HIGH"
    if report_date or has_flow:
        return "MEDIUM"
    return "LOW"


def parse_flow_report_text(text: str) -> dict[str, Any]:
    cleaned = _preprocess_flow_text(text)
    report_date = _extract_report_date(cleaned)

    overview_block = _section_text(cleaned, "overview")
    overview_bullets = _parse_bullets(overview_block)

    notable_rows = _parse_notable_rows(cleaned)

    sector_stats: list[dict[str, object]] = []
    sector_block = _section_text(cleaned, "sector_stats")
    search_text = sector_block or cleaned
    for match in _SECTOR_STAT.finditer(search_text):
        sector_stats.append(
            {
                "sector": match.group(1).strip(),
                "avg_delta_percentile": int(match.group(2)),
            }
        )

    directional_table = _parse_positioning_table(_section_text(cleaned, "directional"))
    large_trades = _parse_trade_lines(_section_text(cleaned, "large_trades"))
    unusual_positions = _parse_trade_lines(_section_text(cleaned, "unusual"))
    top_symbols = _derive_top_symbols(
        notable_rows,
        directional_table,
        large_trades,
        unusual_positions,
    )

    return {
        "kind": "flow_report",
        "proprietary": True,
        "private": True,
        "report_date": report_date,
        "overview_bullets": overview_bullets,
        "index_positioning_summary": _section_text(cleaned, "index_positioning"),
        "stock_positioning_summary": _section_text(cleaned, "stock_positioning"),
        "sector_mix": _parse_sector_breakdown(_section_text(cleaned, "sector_mix")),
        "directional_table": directional_table,
        "gamma_table": _parse_positioning_table(_section_text(cleaned, "gamma")),
        "volatility_table": _parse_positioning_table(_section_text(cleaned, "volatility")),
        "large_trades": large_trades,
        "index_trades": _parse_trade_lines(_section_text(cleaned, "index_trades")),
        "unusual_positions": unusual_positions,
        "notable_positions": notable_rows,
        "sector_stats": sector_stats,
        "algo_flow": _section_text(cleaned, "algo"),
        "top_symbols": top_symbols,
        "parse_confidence": _parse_confidence(
            report_date=report_date,
            overview_bullets=overview_bullets,
            notable_rows=notable_rows,
            top_symbols=top_symbols,
        ),
    }
