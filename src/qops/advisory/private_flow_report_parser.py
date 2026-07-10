"""Parse private flow report text extracted from vendor PDFs."""

from __future__ import annotations

import re
from typing import Any

from qops.ingest.spotgamma_loader import parse_numeric, parse_symbol

_REPORT_DATE = re.compile(
    r"Report\s+Date:\s*([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})",
    re.IGNORECASE,
)
_NOTABLE_ROW = re.compile(
    r"^([A-Z][A-Z0-9.]{0,5})\s+([A-Za-z][A-Za-z\s/&-]+?)\s+\$?([\d.]+)M,\s*(\d+)(?:st|nd|rd|th)?\s*$",
    re.MULTILINE,
)
_SECTOR_STAT = re.compile(
    r"^([A-Za-z][A-Za-z\s/&-]+?)\s+avg\s+delta\s+percentile\s+(\d+)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_SECTION_HEADERS = (
    "Overview",
    "Index Positioning Summary",
    "Stock Positioning Summary",
    "Sector Mix",
    "Directional Table",
    "Gamma Table",
    "Volatility Table",
    "Large Trades",
    "Index Trades",
    "Unusual Positions",
    "Notable Positions",
    "Sector Stats",
    "Algo Flow",
)

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


def _month_to_iso(month_name: str, day: str, year: str) -> str:
    month_num = _MONTHS.get(month_name.lower())
    if month_num is None:
        return ""
    return f"{year}-{month_num:02d}-{int(day):02d}"


def _section_text(text: str, header: str) -> str:
    start = text.lower().find(header.lower())
    if start < 0:
        return ""
    start += len(header)
    end = len(text)
    for other in _SECTION_HEADERS:
        if other.lower() == header.lower():
            continue
        idx = text.lower().find(other.lower(), start)
        if idx >= 0:
            end = min(end, idx)
    return text[start:end].strip()


def _parse_bullets(block: str) -> list[str]:
    bullets: list[str] = []
    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(("-", "•", "*")):
            bullets.append(line.lstrip("-•* ").strip())
        elif not bullets and line:
            bullets.append(line)
    return bullets


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


def parse_flow_report_text(text: str) -> dict[str, Any]:
    report_date = ""
    date_match = _REPORT_DATE.search(text)
    if date_match:
        report_date = _month_to_iso(date_match.group(1), date_match.group(2), date_match.group(3))

    overview_block = _section_text(text, "Overview")
    notable_rows: list[dict[str, object]] = []
    for match in _NOTABLE_ROW.finditer(text):
        symbol = parse_symbol(match.group(1))
        if not symbol:
            continue
        notable_rows.append(
            {
                "symbol": symbol,
                "sector": match.group(2).strip(),
                "delta_mm": float(match.group(3)),
                "delta_percentile": int(match.group(4)),
            }
        )

    sector_stats: list[dict[str, object]] = []
    sector_block = _section_text(text, "Sector Stats")
    search_text = sector_block or text
    for match in _SECTOR_STAT.finditer(search_text):
        sector_stats.append(
            {
                "sector": match.group(1).strip(),
                "avg_delta_percentile": int(match.group(2)),
            }
        )

    top_symbols: list[str] = []
    for row in notable_rows:
        sym = str(row["symbol"])
        if sym not in top_symbols:
            top_symbols.append(sym)

    return {
        "kind": "flow_report",
        "proprietary": True,
        "private": True,
        "report_date": report_date,
        "overview_bullets": _parse_bullets(overview_block),
        "index_positioning_summary": _section_text(text, "Index Positioning Summary"),
        "stock_positioning_summary": _section_text(text, "Stock Positioning Summary"),
        "sector_mix": _parse_sector_breakdown(_section_text(text, "Sector Mix")),
        "directional_table": _parse_positioning_table(_section_text(text, "Directional Table")),
        "gamma_table": _parse_positioning_table(_section_text(text, "Gamma Table")),
        "volatility_table": _parse_positioning_table(_section_text(text, "Volatility Table")),
        "large_trades": _parse_trade_lines(_section_text(text, "Large Trades")),
        "index_trades": _parse_trade_lines(_section_text(text, "Index Trades")),
        "unusual_positions": _parse_trade_lines(_section_text(text, "Unusual Positions")),
        "notable_positions": notable_rows,
        "sector_stats": sector_stats,
        "algo_flow": _section_text(text, "Algo Flow"),
        "top_symbols": top_symbols[:10],
        "parse_confidence": "HIGH" if report_date and notable_rows else "LOW",
    }
