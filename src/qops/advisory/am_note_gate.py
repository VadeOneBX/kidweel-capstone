"""AM Founder Note macro context gate (advisory degradation; non-blocking)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pandas as pd

from qops.backtest.spotgamma_replay_builder import parse_notes_kv
from qops.ingest.spotgamma_loader import parse_numeric

AmNoteStatus = Literal[
    "NOT_AVAILABLE",
    "AVAILABLE_NOT_PARSED",
    "PARSED",
    "STALE",
    "MANUAL_OVERRIDE",
]

MacroContextState = Literal[
    "PRE_AM_NOTE_CONTEXT_INCOMPLETE",
    "AM_NOTE_CONTEXT_READY",
    "AM_NOTE_STALE_REVIEW_REQUIRED",
    "MANUAL_CONTEXT_OVERRIDE",
]

MacroContextStatus = Literal[
    "MACRO_CONTEXT_READY",
    "MACRO_CONTEXT_READY_LOW_CONFIDENCE",
    "MACRO_CONTEXT_UNPARSED_NON_BLOCKING",
    "MACRO_CONTEXT_MISSING_NON_BLOCKING",
    "MANUAL_CONTEXT_OVERRIDE",
]

MacroParseStatus = Literal[
    "STRUCTURED_PARSED",
    "XLSX_FOUNDER_NOTE_PARSED",
    "AVAILABLE_NOT_PARSED",
    "MISSING_OPTIONAL_CONTEXT",
    "NOT_AVAILABLE",
    "MANUAL_OVERRIDE_PARSED",
    "STALE",
]

MacroSourceType = Literal[
    "manual_macro_context_override",
    "structured_sidecar",
    "xlsx_founders_note",
    "unparsed",
    "missing",
]

PAPER_GATE_AM_NOTE_INCOMPLETE = "paper_gate:am_note_context_incomplete"

_XLSX_FOUNDER_FALLBACK_WARNING = (
    "Founder's Note parsed from workbook prose fallback; "
    "structured AM-note sidecar not present."
)
_MANUAL_OVERRIDE_WARNING = "Manual macro context override used."

_FOUNDER_LABEL_RE = re.compile(
    r"^\s*(?:founder's\s+note|founders\s+note|founder\s+note|am\s+note|morning\s+note)\s*:?\s*$",
    re.IGNORECASE,
)
_SECTION_STOP_RE = re.compile(
    r"^\s*(?:what traders should know|executive summary|index etf|sg summary|"
    r"macro theme|key dates|key sg levels|resistance:|support:|pivot:)\b",
    re.IGNORECASE,
)

_AM_NOTE_PARSED_KEYS = frozenset(
    {
        "market_direction_summary",
        "overnight_risk_summary",
        "dealer_support_summary",
        "dealer_risk_summary",
        "key_support_area",
        "key_downside_area",
        "key_upside_area",
        "macro_catalysts",
        "event_risk_window",
        "advisory_bias",
        "spread_posture",
        "call_positioning_risk",
    }
)

_RUN_ID_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


@dataclass(frozen=True, slots=True)
class AmNoteParsed:
    market_direction_summary: str = ""
    overnight_risk_summary: str = ""
    dealer_support_summary: str = ""
    dealer_risk_summary: str = ""
    key_support_area: str = ""
    key_downside_area: str = ""
    key_upside_area: str = ""
    macro_catalysts: tuple[str, ...] = ()
    event_risk_window: str = ""
    advisory_bias: str = ""
    spread_posture: str = ""
    call_positioning_risk: str = ""
    note_trade_date: str = ""


@dataclass(frozen=True, slots=True)
class MacroContextAudit:
    status: MacroContextStatus
    source_type: MacroSourceType
    parse_status: MacroParseStatus
    source_file: str = ""
    warnings: tuple[str, ...] = ()
    confidence: str = "LOW"


@dataclass(frozen=True, slots=True)
class MacroPaperGate:
    am_note_status: AmNoteStatus
    macro_context_state: MacroContextState
    paper_gate_macro_status: str
    macro_context_summary: str
    dealer_positioning_summary: str
    macro_catalyst_summary: str
    spread_posture: str
    am_note_required_before_paper: bool
    parsed_note: AmNoteParsed | None = None
    paper_approval_allowed: bool = False
    macro_context: MacroContextAudit = field(
        default_factory=lambda: MacroContextAudit(
            status="MACRO_CONTEXT_MISSING_NON_BLOCKING",
            source_type="missing",
            parse_status="MISSING_OPTIONAL_CONTEXT",
            confidence="LOW",
        )
    )

def run_date_from_run_id(run_id: str) -> str:
    match = _RUN_ID_DATE.match(run_id.strip())
    return match.group(1) if match else ""


def macro_context_override_path(base_dir: Path, run_id: str) -> Path:
    return base_dir / "data/advisory" / f"{run_id}_macro_context_override.json"


def _is_morning_regime_path(path: Path) -> bool:
    stem = path.stem.lower()
    return stem == "morning_regime" or stem.endswith("_morning_regime") or "morning_regime" in stem


def discover_morning_regime_paths(
    base_dir: Path,
    *,
    run_date: str,
    staged_files: list[str] | None = None,
) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()
    if staged_files:
        for raw in staged_files:
            p = Path(raw)
            if p.is_file() and _is_morning_regime_path(p):
                key = str(p.resolve())
                if key not in seen:
                    seen.add(key)
                    found.append(p)
    if run_date:
        staging = base_dir / "data/spotgamma/staging"
        if staging.is_dir():
            for pattern in (f"{run_date}_morning_regime.*", f"{run_date}_*morning_regime*"):
                for p in staging.glob(pattern):
                    if p.is_file():
                        key = str(p.resolve())
                        if key not in seen:
                            seen.add(key)
                            found.append(p)
    return found


def _load_override(base_dir: Path, run_id: str) -> dict[str, object] | None:
    path = macro_context_override_path(base_dir, run_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _normalize_catalysts(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, list):
        return tuple(str(v).strip() for v in value if str(v).strip())
    text = str(value).strip()
    if not text:
        return ()
    if ";" in text:
        return tuple(part.strip() for part in text.split(";") if part.strip())
    return (text,)


def _row_to_parsed(row: dict[str, object], trade_date: str = "") -> AmNoteParsed:
    return AmNoteParsed(
        market_direction_summary=str(row.get("market_direction_summary", "") or "").strip(),
        overnight_risk_summary=str(row.get("overnight_risk_summary", "") or "").strip(),
        dealer_support_summary=str(row.get("dealer_support_summary", "") or "").strip(),
        dealer_risk_summary=str(row.get("dealer_risk_summary", "") or "").strip(),
        key_support_area=str(row.get("key_support_area", "") or "").strip(),
        key_downside_area=str(row.get("key_downside_area", "") or "").strip(),
        key_upside_area=str(row.get("key_upside_area", "") or "").strip(),
        macro_catalysts=_normalize_catalysts(row.get("macro_catalysts")),
        event_risk_window=str(row.get("event_risk_window", "") or "").strip(),
        advisory_bias=str(row.get("advisory_bias", "") or "").strip(),
        spread_posture=str(row.get("spread_posture", "") or "").strip(),
        call_positioning_risk=str(row.get("call_positioning_risk", "") or "").strip(),
        note_trade_date=trade_date,
    )


def _parsed_is_complete(parsed: AmNoteParsed) -> bool:
    required_text = (
        parsed.market_direction_summary,
        parsed.dealer_support_summary,
        parsed.dealer_risk_summary,
        parsed.advisory_bias,
        parsed.spread_posture,
    )
    return all(bool(x.strip()) for x in required_text)


def parse_am_note_file(path: Path, *, session_date: str = "") -> AmNoteParsed | None:
    """Parse structured AM-note sidecar (.json / .csv only). XLSX handled separately."""
    if not path.is_file():
        return None
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if isinstance(data, dict):
            note_date = str(data.get("trade_date", "") or session_date).strip()
            return _row_to_parsed(data, trade_date=note_date)
        return None
    if suffix == ".csv":
        try:
            df = pd.read_csv(path)
        except (OSError, pd.errors.ParserError):
            return None
        if df.empty:
            return None
        cols = {c.lower(): c for c in df.columns}
        if "field" in cols and "value" in cols:
            row_map: dict[str, object] = {}
            fcol, vcol = cols["field"], cols["value"]
            for _, series in df.iterrows():
                key = str(series.get(fcol, "")).strip()
                if key:
                    row_map[key] = series.get(vcol)
            return _row_to_parsed(row_map, trade_date=session_date)
        first = df.iloc[0]
        row_dict = {str(k): first[k] for k in df.columns}
        normalized = {k.lower(): v for k, v in row_dict.items()}
        if any(k in normalized for k in _AM_NOTE_PARSED_KEYS):
            return _row_to_parsed(
                {k: normalized.get(k, "") for k in _AM_NOTE_PARSED_KEYS},
                trade_date=session_date,
            )
        return None
    return None


def _cell_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none"}:
        return ""
    return text


def parse_xlsx_founders_note(path: Path, *, session_date: str = "") -> AmNoteParsed | None:
    """Extract Founder's Note prose from morning_regime.xlsx without inventing bias/posture."""
    if not path.is_file() or path.suffix.lower() not in {".xlsx", ".xls"}:
        return None
    try:
        xl = pd.ExcelFile(path)
    except (OSError, ValueError):
        return None

    sheet_name = None
    for name in xl.sheet_names:
        if str(name).strip().lower() == "morning_regime":
            sheet_name = name
            break
    if sheet_name is None:
        sheet_name = xl.sheet_names[0] if xl.sheet_names else None
    if sheet_name is None:
        return None

    try:
        df = pd.read_excel(path, sheet_name=sheet_name, header=None)
    except (OSError, ValueError):
        return None
    if df.empty:
        return None

    label_row: int | None = None
    for idx in range(len(df)):
        for col in range(df.shape[1]):
            cell = _cell_text(df.iat[idx, col])
            if cell and _FOUNDER_LABEL_RE.match(cell):
                label_row = idx
                break
        if label_row is not None:
            break
    if label_row is None:
        return None

    prose_parts: list[str] = []
    for idx in range(label_row + 1, len(df)):
        row_texts: list[str] = []
        for col in range(df.shape[1]):
            cell = _cell_text(df.iat[idx, col])
            if cell:
                row_texts.append(cell)
        if not row_texts:
            if prose_parts:
                break
            continue
        joined = " ".join(row_texts)
        if _SECTION_STOP_RE.match(joined) and prose_parts:
            break
        if _FOUNDER_LABEL_RE.match(joined):
            continue
        prose_parts.append(joined)

    prose = " ".join(prose_parts).strip()
    if not prose:
        return None

    return AmNoteParsed(
        market_direction_summary=prose,
        dealer_support_summary="",
        dealer_risk_summary="",
        advisory_bias="UNKNOWN",
        spread_posture="UNKNOWN",
        note_trade_date=session_date,
    )


def _structured_sidecar_paths(paths: list[Path]) -> list[Path]:
    return [p for p in paths if p.suffix.lower() in {".json", ".csv"}]


def _xlsx_paths(paths: list[Path]) -> list[Path]:
    return [p for p in paths if p.suffix.lower() in {".xlsx", ".xls"}]


def resolve_am_note_status(
    paths: list[Path],
    *,
    session_date: str,
    override: dict[str, object] | None,
) -> tuple[AmNoteStatus, AmNoteParsed | None]:
    """Legacy resolver retained for tests; prefer resolve_macro_context_resolution."""
    resolution = resolve_macro_context_resolution(
        paths,
        session_date=session_date,
        override=override,
        override_path=None,
    )
    return resolution.am_note_status, resolution.parsed_note


@dataclass(frozen=True, slots=True)
class MacroContextResolution:
    am_note_status: AmNoteStatus
    parsed_note: AmNoteParsed | None
    macro_context: MacroContextAudit


def resolve_macro_context_resolution(
    paths: list[Path],
    *,
    session_date: str,
    override: dict[str, object] | None,
    override_path: Path | None,
) -> MacroContextResolution:
    """Priority: manual override → structured sidecar → XLSX Founder's Note → degrade."""
    if override:
        status_raw = str(override.get("am_note_status", "") or "").strip().upper()
        if status_raw == "MANUAL_OVERRIDE" or bool(override.get("manual_override")):
            parsed = None
            if override.get("parsed_note") and isinstance(override["parsed_note"], dict):
                parsed = _row_to_parsed(override["parsed_note"], trade_date=session_date)
            source = str(override_path) if override_path is not None else ""
            return MacroContextResolution(
                am_note_status="MANUAL_OVERRIDE",
                parsed_note=parsed,
                macro_context=MacroContextAudit(
                    status="MANUAL_CONTEXT_OVERRIDE",
                    source_type="manual_macro_context_override",
                    parse_status="MANUAL_OVERRIDE_PARSED",
                    source_file=source,
                    warnings=(_MANUAL_OVERRIDE_WARNING,),
                    confidence="HIGH",
                ),
            )

    structured = _structured_sidecar_paths(paths)
    for path in structured:
        parsed = parse_am_note_file(path, session_date=session_date)
        if parsed is None:
            continue
        if not _parsed_is_complete(parsed):
            continue
        note_date = (parsed.note_trade_date or session_date).strip()
        if session_date and note_date and note_date < session_date:
            return MacroContextResolution(
                am_note_status="STALE",
                parsed_note=parsed,
                macro_context=MacroContextAudit(
                    status="MACRO_CONTEXT_READY_LOW_CONFIDENCE",
                    source_type="structured_sidecar",
                    parse_status="STALE",
                    source_file=str(path),
                    warnings=("Structured AM-note sidecar is stale relative to session date.",),
                    confidence="MEDIUM",
                ),
            )
        return MacroContextResolution(
            am_note_status="PARSED",
            parsed_note=parsed,
            macro_context=MacroContextAudit(
                status="MACRO_CONTEXT_READY",
                source_type="structured_sidecar",
                parse_status="STRUCTURED_PARSED",
                source_file=str(path),
                warnings=(),
                confidence="HIGH",
            ),
        )

    xlsx_candidates = _xlsx_paths(paths)
    for path in xlsx_candidates:
        parsed = parse_xlsx_founders_note(path, session_date=session_date)
        if parsed is None:
            continue
        return MacroContextResolution(
            am_note_status="PARSED",
            parsed_note=parsed,
            macro_context=MacroContextAudit(
                status="MACRO_CONTEXT_READY_LOW_CONFIDENCE",
                source_type="xlsx_founders_note",
                parse_status="XLSX_FOUNDER_NOTE_PARSED",
                source_file=str(path),
                warnings=(_XLSX_FOUNDER_FALLBACK_WARNING,),
                confidence="LOW",
            ),
        )

    if paths:
        return MacroContextResolution(
            am_note_status="AVAILABLE_NOT_PARSED",
            parsed_note=None,
            macro_context=MacroContextAudit(
                status="MACRO_CONTEXT_UNPARSED_NON_BLOCKING",
                source_type="unparsed",
                parse_status="AVAILABLE_NOT_PARSED",
                source_file=str(paths[0]),
                warnings=(
                    "Morning regime present but Founder's Note / AM-note context unparsed; "
                    "non-blocking degradation.",
                ),
                confidence="LOW",
            ),
        )

    return MacroContextResolution(
        am_note_status="NOT_AVAILABLE",
        parsed_note=None,
        macro_context=MacroContextAudit(
            status="MACRO_CONTEXT_MISSING_NON_BLOCKING",
            source_type="missing",
            parse_status="MISSING_OPTIONAL_CONTEXT",
            source_file="",
            warnings=("Optional AM Founder's Note context missing; non-blocking degradation.",),
            confidence="LOW",
        ),
    )


def resolve_macro_context_state(
    am_note_status: AmNoteStatus,
    *,
    override: dict[str, object] | None,
) -> MacroContextState:
    if override:
        state_raw = str(override.get("macro_context_state", "") or "").strip().upper()
        if state_raw == "MANUAL_CONTEXT_OVERRIDE" or am_note_status == "MANUAL_OVERRIDE":
            return "MANUAL_CONTEXT_OVERRIDE"
    if am_note_status == "MANUAL_OVERRIDE":
        return "MANUAL_CONTEXT_OVERRIDE"
    if am_note_status == "STALE":
        return "AM_NOTE_STALE_REVIEW_REQUIRED"
    if am_note_status == "PARSED":
        return "AM_NOTE_CONTEXT_READY"
    # Degraded / missing remain advisory-only; legacy state kept for display compatibility.
    return "PRE_AM_NOTE_CONTEXT_INCOMPLETE"


def paper_approval_allowed_for_macro(
    am_note_status: AmNoteStatus,
    macro_context_state: MacroContextState,
) -> bool:
    """AM-note gaps are non-blocking (MORNING-REGIME-DEGRADE-NOT-BLOCK-C1)."""
    del am_note_status, macro_context_state
    return True


def _summaries_from_parsed(parsed: AmNoteParsed | None) -> tuple[str, str, str, str]:
    if parsed is None:
        return "", "", "", ""
    macro = " ".join(
        part
        for part in (
            parsed.market_direction_summary,
            parsed.overnight_risk_summary,
        )
        if part
    ).strip()
    dealer = " ".join(
        part
        for part in (
            parsed.dealer_support_summary,
            parsed.dealer_risk_summary,
            parsed.call_positioning_risk,
        )
        if part
    ).strip()
    catalysts = "; ".join(parsed.macro_catalysts)
    if parsed.event_risk_window:
        catalysts = f"{catalysts}; window={parsed.event_risk_window}".strip("; ")
    posture = parsed.spread_posture
    return macro, dealer, catalysts, posture


def build_macro_paper_gate(
    base_dir: Path,
    *,
    run_id: str,
    staged_files: list[str] | None = None,
) -> MacroPaperGate:
    session_date = run_date_from_run_id(run_id)
    override_path = macro_context_override_path(base_dir, run_id)
    override = _load_override(base_dir, run_id)
    paths = discover_morning_regime_paths(
        base_dir,
        run_date=session_date,
        staged_files=staged_files,
    )
    resolution = resolve_macro_context_resolution(
        paths,
        session_date=session_date,
        override=override,
        override_path=override_path if override is not None else None,
    )
    am_status = resolution.am_note_status
    parsed = resolution.parsed_note
    audit = resolution.macro_context
    macro_state = resolve_macro_context_state(am_status, override=override)
    allowed = paper_approval_allowed_for_macro(am_status, macro_state)

    macro_summary, dealer_summary, catalyst_summary, spread_posture = _summaries_from_parsed(
        parsed
    )

    if audit.status == "MANUAL_CONTEXT_OVERRIDE":
        paper_gate_status = "manual_macro_context_override"
        macro_context_summary = macro_summary or "Operator recorded manual macro context override."
    elif audit.parse_status == "STRUCTURED_PARSED":
        paper_gate_status = "am_note_context_ready"
        bias = parsed.advisory_bias if parsed else ""
        macro_context_summary = (
            f"AM note parsed. Macro posture is {bias or 'reviewed'}. {macro_summary}"
        ).strip()
    elif audit.parse_status == "XLSX_FOUNDER_NOTE_PARSED":
        paper_gate_status = "am_note_xlsx_founder_fallback"
        macro_context_summary = (
            "Founder's Note prose parsed from morning_regime.xlsx at low confidence. "
            f"{macro_summary}"
        ).strip()
    elif audit.parse_status == "STALE":
        paper_gate_status = "am_note_stale_review_required"
        macro_context_summary = (
            "AM note is stale relative to session date; advisory confidence reduced "
            "(non-blocking)."
        )
    elif audit.status == "MACRO_CONTEXT_UNPARSED_NON_BLOCKING":
        paper_gate_status = "am_note_present_unparsed_non_blocking"
        macro_context_summary = (
            "Founder's Note / AM-note context unparsed; morning loop continues with "
            "degraded macro confidence."
        )
    else:
        paper_gate_status = "am_note_missing_non_blocking"
        macro_context_summary = (
            "Optional AM Founder's Note context missing; morning loop continues with "
            "degraded macro confidence."
        )

    if not spread_posture:
        if audit.parse_status == "XLSX_FOUNDER_NOTE_PARSED":
            spread_posture = "UNKNOWN"
        elif audit.parse_status in {"STRUCTURED_PARSED", "MANUAL_OVERRIDE_PARSED"}:
            spread_posture = ""
        else:
            spread_posture = (
                "retain candidates; macro context degraded (Founder's Note optional)"
            )

    return MacroPaperGate(
        am_note_status=am_status,
        macro_context_state=macro_state,
        paper_gate_macro_status=paper_gate_status,
        macro_context_summary=macro_context_summary,
        dealer_positioning_summary=dealer_summary,
        macro_catalyst_summary=catalyst_summary,
        spread_posture=spread_posture,
        am_note_required_before_paper=False,
        parsed_note=parsed,
        paper_approval_allowed=allowed,
        macro_context=audit,
    )


def apply_am_note_paper_gate_to_audit(
    audit_df: pd.DataFrame,
    gate: MacroPaperGate,
) -> pd.DataFrame:
    """AM-note incompleteness no longer withholds paper approval (degrade-not-block)."""
    del gate
    return audit_df


@dataclass(frozen=True, slots=True)
class PreAmStructureFields:
    negative_gamma_detected: bool
    gamma_regime_label: str
    put_wall_current: float | None
    put_wall_prior: float | None
    put_wall_change: float | None
    call_wall_current: float | None
    call_wall_prior: float | None
    call_wall_change: float | None
    spot_vs_put_wall: str
    spot_vs_call_wall: str
    gamma_ratio_current: float | None
    gamma_ratio_prior: float | None
    gamma_ratio_change: float | None
    iv_rv_state: str
    macro_event_pending: bool
    pre_note_advisory_summary: str


def _spy_snapshots_from_context(context_df: pd.DataFrame) -> list[dict[str, object]]:
    if context_df.empty:
        return []
    df = context_df.copy()
    if "symbol" in df.columns:
        df = df[df["symbol"].astype(str).str.upper() == "SPY"]
    elif "source_profile" in df.columns:
        df = df[df["source_profile"].astype(str).isin({"spy_history", "spy_excel"})]
    else:
        return []

    rows: list[dict[str, object]] = []
    for _, series in df.iterrows():
        notes = parse_notes_kv(str(series.get("notes", "") or ""))
        trade_date = str(series.get("trade_date", "") or "").strip()
        if not trade_date:
            continue
        spot = parse_numeric(notes.get("current_price"))
        if spot is None:
            spot = parse_numeric(series.get("gamma_ratio"))
        rows.append(
            {
                "trade_date": trade_date,
                "spot": spot,
                "call_wall": parse_numeric(notes.get("call_wall")),
                "put_wall": parse_numeric(notes.get("put_wall")),
                "hedge_wall": parse_numeric(notes.get("hedge_wall")),
                "gamma_ratio": parse_numeric(series.get("gamma_ratio")),
                "one_month_iv": parse_numeric(notes.get("one_month_iv")),
                "one_month_rv": parse_numeric(notes.get("one_month_rv")),
                "iv_rank": parse_numeric(series.get("iv_rank")),
            }
        )
    rows.sort(key=lambda r: str(r["trade_date"]))
    return rows


def _spot_vs_wall(spot: float | None, wall: float | None) -> str:
    if spot is None or wall is None:
        return "UNKNOWN"
    if spot > wall:
        return "ABOVE"
    if spot < wall:
        return "BELOW"
    return "AT"


def build_pre_am_structure_fields(context_df: pd.DataFrame) -> PreAmStructureFields:
    snaps = _spy_snapshots_from_context(context_df)
    if not snaps:
        return PreAmStructureFields(
            negative_gamma_detected=False,
            gamma_regime_label="UNKNOWN_GAMMA_STATE",
            put_wall_current=None,
            put_wall_prior=None,
            put_wall_change=None,
            call_wall_current=None,
            call_wall_prior=None,
            call_wall_change=None,
            spot_vs_put_wall="UNKNOWN",
            spot_vs_call_wall="UNKNOWN",
            gamma_ratio_current=None,
            gamma_ratio_prior=None,
            gamma_ratio_change=None,
            iv_rv_state="UNKNOWN",
            macro_event_pending=False,
            pre_note_advisory_summary=(
                "Pre-AM note structure unavailable from SPY context; wait for Founder note."
            ),
        )

    current = snaps[-1]
    prior = snaps[-2] if len(snaps) >= 2 else None

    gr_current = current.get("gamma_ratio")
    gr_prior = prior.get("gamma_ratio") if prior else None
    gr_change = None
    if gr_current is not None and gr_prior is not None:
        gr_change = float(gr_current) - float(gr_prior)

    put_c = current.get("put_wall")
    put_p = prior.get("put_wall") if prior else None
    call_c = current.get("call_wall")
    call_p = prior.get("call_wall") if prior else None

    def _delta(cur: object, prev: object) -> float | None:
        if cur is None or prev is None:
            return None
        return float(cur) - float(prev)

    negative = False
    gamma_label = "UNKNOWN_GAMMA_STATE"
    if gr_current is not None:
        if float(gr_current) < 1.0:
            negative = True
            gamma_label = "NEGATIVE_GAMMA_UNSTABLE"
        elif float(gr_current) >= 1.0:
            gamma_label = "POSITIVE_GAMMA_STABLE"
    hedge = current.get("hedge_wall")
    spot = current.get("spot")
    if hedge is not None and spot is not None and float(spot) < float(hedge):
        negative = True
        if gamma_label == "POSITIVE_GAMMA_STABLE":
            gamma_label = "TRANSITIONAL_GAMMA"

    iv = current.get("one_month_iv")
    rv = current.get("one_month_rv")
    iv_rv_state = "UNKNOWN"
    if iv is not None and rv is not None:
        iv_rv_state = "IV_ABOVE_RV" if float(iv) > float(rv) else "IV_AT_OR_BELOW_RV"

    summary = (
        "Pre-AM note structure is defensive. Gamma regime appears unstable; treat directional "
        "bull call spreads with caution while macro confidence is degraded. Candidates may "
        "proceed with advisory warnings."
        if negative or gamma_label in {"NEGATIVE_GAMMA_UNSTABLE", "TRANSITIONAL_GAMMA"}
        else (
            "Pre-AM note structure is mixed; retain candidates and treat Founder's Note prose "
            "as optional low-confidence macro enrichment."
        )
    )

    return PreAmStructureFields(
        negative_gamma_detected=negative,
        gamma_regime_label=gamma_label,
        put_wall_current=None if put_c is None else float(put_c),
        put_wall_prior=None if put_p is None else float(put_p),
        put_wall_change=_delta(put_c, put_p),
        call_wall_current=None if call_c is None else float(call_c),
        call_wall_prior=None if call_p is None else float(call_p),
        call_wall_change=_delta(call_c, call_p),
        spot_vs_put_wall=_spot_vs_wall(
            None if spot is None else float(spot),
            None if put_c is None else float(put_c),
        ),
        spot_vs_call_wall=_spot_vs_wall(
            None if spot is None else float(spot),
            None if call_c is None else float(call_c),
        ),
        gamma_ratio_current=None if gr_current is None else float(gr_current),
        gamma_ratio_prior=None if gr_prior is None else float(gr_prior),
        gamma_ratio_change=gr_change,
        iv_rv_state=iv_rv_state,
        macro_event_pending=False,
        pre_note_advisory_summary=summary,
    )
