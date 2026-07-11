"""Build sanitized advisory context from private vendor parsed JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

LaneStatus = Literal[
    "READY",
    "READY_LOW_CONFIDENCE",
    "PARTIAL",
    "MISSING_NON_BLOCKING",
    "PARSE_FAILED_NON_BLOCKING",
]

PRIVATE_PARSED_ROOT = Path("private/parsed")


def _field_present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return True


def _has_gate_levels(parsed: dict[str, Any]) -> bool:
    return any(
        parsed.get(k) is not None
        for k in ("call_wall", "put_wall", "zero_gamma_level", "volatility_trigger")
    )


def _lane_status(
    parsed: dict[str, Any] | None,
    *,
    required_fields: tuple[str, ...],
) -> LaneStatus:
    """Map parsed private JSON to a readiness lane.

    MISSING = file/object absent.
    PARSE_FAILED = present but NEEDS_REVIEW or no usable fields.
    PARTIAL = present with some usable fields.
    READY / READY_LOW_CONFIDENCE = required fields present.
    """
    if parsed is None:
        return "MISSING_NON_BLOCKING"
    if parsed.get("parse_status") == "NEEDS_REVIEW":
        return "PARSE_FAILED_NON_BLOCKING"

    confidence = str(parsed.get("parse_confidence", "") or "").upper()
    missing_required = [f for f in required_fields if not _field_present(parsed.get(f))]
    any_required = any(_field_present(parsed.get(f)) for f in required_fields)

    if not missing_required:
        # Required content present. Missing report_date alone must not fail the lane
        # (flow reports may omit date while still carrying bullets/symbols).
        if confidence in {"LOW", "MEDIUM"}:
            return "READY_LOW_CONFIDENCE"
        return "READY"

    if any_required:
        return "PARTIAL"

    # No required fields, but artifact may still carry usable alternate signals.
    if _has_gate_levels(parsed) or _field_present(parsed.get("report_date")):
        return "PARTIAL"

    return "PARSE_FAILED_NON_BLOCKING"


def _truncate(text: str, limit: int = 240) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _load_private_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def discover_private_parsed_paths(
    base_dir: Path,
    *,
    run_date: str,
) -> tuple[Path | None, Path | None]:
    """Return (macro_note_path, flow_report_path) for a session date."""
    if not run_date:
        return None, None
    stem_date = run_date.replace("-", "_")
    parsed_dir = base_dir / PRIVATE_PARSED_ROOT
    macro = parsed_dir / f"macro_note_{stem_date}.json"
    flow = parsed_dir / f"flow_report_{stem_date}.json"
    return (
        macro if macro.is_file() else None,
        flow if flow.is_file() else None,
    )


def build_sanitized_advisory_context(
    *,
    macro_note: dict[str, Any] | None = None,
    flow_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Produce operator-safe advisory context without proprietary prose or tables."""
    macro_status = _lane_status(
        macro_note,
        required_fields=("macro_theme", "macro_note_summary"),
    )
    flow_status = _lane_status(
        flow_report,
        required_fields=("overview_bullets", "top_symbols"),
    )
    skew_status = _lane_status(
        macro_note,
        required_fields=("skew_commentary", "risk_reversal_25d"),
    )
    vol_status = _lane_status(
        macro_note,
        required_fields=("volatility_trigger", "implied_1d_move_pct"),
    )
    index_status = _lane_status(
        macro_note,
        required_fields=("call_wall", "put_wall", "zero_gamma_level"),
    )

    summary_parts: list[str] = []
    if macro_note:
        theme = str(macro_note.get("macro_theme", "") or "").strip()
        if theme:
            summary_parts.append(_truncate(f"Macro: {theme}", 120))
        levels = macro_note.get("index_levels") or {}
        if isinstance(levels, dict):
            res = levels.get("resistance")
            sup = levels.get("support")
            if res is not None and sup is not None:
                summary_parts.append(f"Index range ref resistance={res} support={sup}")
    if flow_report:
        bullets = flow_report.get("overview_bullets") or []
        if bullets and isinstance(bullets, list):
            summary_parts.append(_truncate(f"Flow: {bullets[0]}", 120))
        top_syms = flow_report.get("top_symbols") or []
        if top_syms:
            summary_parts.append("Top symbols: " + ", ".join(str(s) for s in top_syms[:5]))

    gate_levels: dict[str, float | None] = {}
    if macro_note:
        for key in (
            "call_wall",
            "put_wall",
            "zero_gamma_level",
            "volatility_trigger",
            "absolute_gamma_strike",
        ):
            val = macro_note.get(key)
            gate_levels[key] = float(val) if val is not None else None
        levels = macro_note.get("index_levels")
        if isinstance(levels, dict):
            for k, v in levels.items():
                gate_levels[f"index_{k}"] = float(v) if v is not None else None

    top_sectors: list[str] = []
    if flow_report:
        for row in flow_report.get("sector_stats") or []:
            if isinstance(row, dict) and row.get("sector"):
                top_sectors.append(str(row["sector"]))

    return {
        "source_presence": {
            "macro_note": macro_note is not None,
            "flow_report": flow_report is not None,
        },
        "parse_confidence": {
            "macro_note": (macro_note or {}).get("parse_confidence", "MISSING"),
            "flow_report": (flow_report or {}).get("parse_confidence", "MISSING"),
        },
        "lanes": {
            "macro_context": macro_status,
            "flow_context": flow_status,
            "skew_context": skew_status,
            "vol_context": vol_status,
            "index_levels_context": index_status,
        },
        "operator_safe_summary": ". ".join(summary_parts),
        "gate_levels": gate_levels,
        "top_symbols": list((flow_report or {}).get("top_symbols") or [])[:10],
        "top_sectors": top_sectors[:5],
        "disclaimer": "Private vendor-derived context; proprietary source redacted. Not investment advice.",
    }


def load_sanitized_private_context(
    base_dir: Path,
    *,
    run_date: str,
) -> dict[str, Any]:
    macro_path, flow_path = discover_private_parsed_paths(base_dir, run_date=run_date)
    macro = _load_private_json(macro_path) if macro_path else None
    flow = _load_private_json(flow_path) if flow_path else None
    ctx = build_sanitized_advisory_context(macro_note=macro, flow_report=flow)
    stem_date = run_date.replace("-", "_") if run_date else ""
    ctx["sources"] = {
        "macro_note": str(macro_path) if macro_path else "",
        "flow_report": str(flow_path) if flow_path else "",
        "source_date": stem_date,
    }
    return ctx
