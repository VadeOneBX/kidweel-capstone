"""Normalize SpotGamma XLSX rows into canonical :class:`SpotGammaRecord` objects."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import pandas as pd

from qops.spotgamma.models import SourceType, SpotGammaRecord

# Canonical field -> acceptable normalized header names (lowercase, underscores).
_FIELD_ALIASES: dict[str, frozenset[str]] = {
    "symbol": frozenset({"symbol", "ticker", "underlying", "sym", "root"}),
    "price": frozenset({"price", "spot", "last", "underlying_price", "stock_price", "current_price"}),
    "vol_trigger": frozenset(
        {"vol_trigger", "voltrigger", "trigger", "vol_trigger_level", "hedge_wall"}
    ),
    "call_wall": frozenset({"call_wall", "callwall", "c_wall", "gamma_call_wall"}),
    "put_wall": frozenset({"put_wall", "putwall", "p_wall", "gamma_put_wall"}),
    "gamma_ratio": frozenset({"gamma_ratio", "gammaratio", "gamma", "net_gamma_ratio"}),
    "vrp": frozenset({"vrp", "vol_risk_premium"}),
    "vrp_z": frozenset({"vrp_z", "vrpz", "z_score", "vrp_zscore"}),
    "iv_rank": frozenset({"iv_rank", "ivrank", "ivr"}),
    "regime_label": frozenset({"regime_label", "regime", "label", "regime_tag"}),
    "confidence": frozenset({"confidence", "conf", "score", "conviction"}),
    "notes": frozenset({"notes", "note", "comment", "comments"}),
}


def _normalize_header(name: str) -> str:
    s = str(name).strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-z0-9_]", "", s)
    return s


def _header_maps_to_field(normalized_header: str) -> str | None:
    for field, aliases in _FIELD_ALIASES.items():
        if normalized_header in aliases:
            return field
    return None


def _build_column_map(columns: list[Any]) -> dict[str, str]:
    """Map canonical field name -> original column label."""
    out: dict[str, str] = {}
    for raw in columns:
        nh = _normalize_header(str(raw))
        field = _header_maps_to_field(nh)
        if field is None:
            continue
        if field in out and out[field] != raw:
            raise ValueError(
                f"Ambiguous columns for field {field!r}: {out[field]!r} and {raw!r}"
            )
        out[field] = str(raw)
    return out


def to_optional_float(value: Any) -> float | None:
    """Convert a cell value to ``float`` or ``None`` if missing or non-numeric."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, str):
        t = value.strip()
        if not t or t.upper() in {"N/A", "NA", "-", "--"}:
            return None
        try:
            return float(t.replace(",", ""))
        except ValueError as e:
            raise ValueError(f"Cannot parse float from {value!r}") from e
    try:
        return float(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Cannot parse float from {value!r}") from e


def to_optional_str(value: Any) -> str | None:
    """Convert a cell value to stripped ``str`` or ``None`` if missing or blank."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    return s if s else None


def parse_notes_cell(value: Any) -> tuple[str, ...]:
    """Parse notes from a cell into a tuple of segments (pipe- or single-line)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ()
    s = str(value).strip()
    if not s:
        return ()
    if "|" in s:
        return tuple(p.strip() for p in s.split("|") if p.strip())
    return (s,)


def require_symbol(value: Any, *, row_index: Any) -> str:
    """Return an uppercased, trimmed symbol or raise."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise ValueError(f"Row {row_index}: symbol is missing or empty")
    out = str(value).strip().upper()
    if not out:
        raise ValueError(f"Row {row_index}: symbol is missing or empty")
    return out


def require_confidence(value: Any, *, row_index: Any) -> float:
    """Parse required confidence as a float."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise ValueError(f"Row {row_index}: confidence is missing")
    try:
        c = float(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Row {row_index}: confidence is not numeric: {value!r}") from e
    return c


def normalize_rows(
    df: pd.DataFrame,
    *,
    source_type: SourceType,
    trade_date: date,
    default_confidence: float | None = None,
) -> list[SpotGammaRecord]:
    """Map a SpotGamma sheet to canonical records.

    Required columns (by header or alias): ``symbol``.

    ``confidence`` column is required unless ``default_confidence`` is set (portal exports
    often omit confidence; pass an explicit default from the CLI rather than inventing one).

    Args:
        df: Raw sheet data.
        source_type: Which export this sheet came from.
        trade_date: Session date for all rows.
        default_confidence: If the sheet has no confidence column, use this value for every row.

    Returns:
        One :class:`SpotGammaRecord` per data row.

    Raises:
        ValueError: If required columns are missing, headers are ambiguous, or a row
            fails validation (empty symbol or missing confidence).
    """
    col_map = _build_column_map(list(df.columns))
    if "symbol" not in col_map:
        raise ValueError(
            "Required column for symbol not found (expected one of: "
            f"{sorted(_FIELD_ALIASES['symbol'])}). Got columns: {list(df.columns)}"
        )
    use_default_confidence = False
    if "confidence" not in col_map:
        if default_confidence is None:
            raise ValueError(
                "Required column for confidence not found (expected one of: "
                f"{sorted(_FIELD_ALIASES['confidence'])}), and default_confidence was not set. "
                f"Got columns: {list(df.columns)}"
            )
        use_default_confidence = True

    sym_col = col_map["symbol"]
    conf_col = col_map["confidence"] if not use_default_confidence else None

    def pick(field: str) -> str | None:
        return col_map.get(field)

    records: list[SpotGammaRecord] = []
    for idx, row in df.iterrows():
        symbol = require_symbol(row[sym_col], row_index=idx)
        if use_default_confidence:
            assert default_confidence is not None
            confidence = float(default_confidence)
        else:
            assert conf_col is not None
            confidence = require_confidence(row[conf_col], row_index=idx)

        price_c = pick("price")
        vol_c = pick("vol_trigger")
        call_c = pick("call_wall")
        put_c = pick("put_wall")
        gr_c = pick("gamma_ratio")
        vrp_c = pick("vrp")
        vrpz_c = pick("vrp_z")
        ivr_c = pick("iv_rank")
        reg_c = pick("regime_label")
        notes_c = pick("notes")

        notes = parse_notes_cell(row[notes_c]) if notes_c else ()
        if use_default_confidence:
            notes = notes + ("confidence:default_scalar_from_cli",)

        records.append(
            SpotGammaRecord(
                trade_date=trade_date,
                symbol=symbol,
                source_type=source_type,
                price=to_optional_float(row[price_c]) if price_c else None,
                vol_trigger=to_optional_float(row[vol_c]) if vol_c else None,
                call_wall=to_optional_float(row[call_c]) if call_c else None,
                put_wall=to_optional_float(row[put_c]) if put_c else None,
                gamma_ratio=to_optional_float(row[gr_c]) if gr_c else None,
                vrp=to_optional_float(row[vrp_c]) if vrp_c else None,
                vrp_z=to_optional_float(row[vrpz_c]) if vrpz_c else None,
                iv_rank=to_optional_float(row[ivr_c]) if ivr_c else None,
                regime_label=to_optional_str(row[reg_c]) if reg_c else None,
                confidence=confidence,
                notes=notes,
            )
        )
    return records
