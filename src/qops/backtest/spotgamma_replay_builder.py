"""Stage replay candidates from SpotGamma context rows (no ReplayContext, no Alpaca)."""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

import pandas as pd

from qops.ingest.spotgamma_loader import parse_numeric
from qops.ingest.spotgamma_normalize import SpotGammaContextRow, build_context_corpus

_CANDIDATE_PROFILES: frozenset[str] = frozenset(
    {"squeeze", "vrp", "reverse_vrp", "processed_weekly"}
)

_RAW_FRESH_PROFILES: frozenset[str] = frozenset(
    {"squeeze", "vrp", "reverse_vrp", "spy_history"}
)

STALE_CONTEXT_CSV_MESSAGE = (
    "Input context appears stale/pre-C1A: missing source_profile/raw profiles. "
    "Re-run examples/spotgamma_replay_corpus.py --include-raw or pass --rebuild-if-stale."
)

_REASON_BY_PROFILE: dict[str, str] = {
    "squeeze": "squeeze_profile_candidate",
    "vrp": "vrp_profile_candidate",
    "reverse_vrp": "reverse_vrp_profile_candidate",
    "processed_weekly": "processed_weekly_candidate",
}


@dataclass(frozen=True, slots=True)
class ContextCsvFreshness:
    """Freshness assessment for a normalized context CSV (post SG-BT-C1A)."""

    is_fresh: bool
    has_source_profile_column: bool
    raw_profiles_found: frozenset[str]


@dataclass(frozen=True, slots=True)
class ReplayCandidateRow:
    symbol: str
    trade_date: str
    source_profile: str
    source_file: str
    current_price: float | None
    gamma_ratio: float | None
    delta_ratio: float | None
    put_call_oi_ratio: float | None
    volume_ratio: float | None
    iv_rank: float | None
    vrp: float | None
    one_month_iv: float | None
    one_month_rv: float | None
    skew: float | None
    ne_skew: float | None
    options_impact: float | None
    options_implied_move: float | None
    call_wall: float | None
    put_wall: float | None
    hedge_wall: float | None
    spy_gamma_ratio: float | None
    spy_delta_ratio: float | None
    spy_put_call_oi_ratio: float | None
    spy_volume_ratio: float | None
    spy_vrp: float | None
    spy_one_month_iv: float | None
    spy_one_month_rv: float | None
    spy_iv_rank: float | None
    spy_skew: float | None
    spy_ne_skew: float | None
    spy_call_wall: float | None
    spy_put_wall: float | None
    spy_hedge_wall: float | None
    candidate_reason: str
    missing_fields: str
    has_spy_context: bool


@dataclass(frozen=True, slots=True)
class _SpyContextSlice:
    gamma_ratio: float | None
    delta_ratio: float | None
    put_call_oi_ratio: float | None
    volume_ratio: float | None
    vrp: float | None
    one_month_iv: float | None
    one_month_rv: float | None
    iv_rank: float | None
    skew: float | None
    ne_skew: float | None
    call_wall: float | None
    put_wall: float | None
    hedge_wall: float | None


def parse_notes_kv(notes: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if not notes or not notes.strip():
        return out
    for part in notes.split("|"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, val = part.split("=", 1)
        out[key.strip()] = val.strip()
    return out


def _note_float(notes: dict[str, str], key: str) -> float | None:
    return parse_numeric(notes.get(key))


def _infer_source_profile(row: pd.Series) -> str:
    if "source_profile" in row.index and pd.notna(row.get("source_profile")):
        return str(row["source_profile"]).strip()
    source_type = str(row.get("source_type", "")).strip().upper()
    source_file = str(row.get("source_file", "")).lower()
    if source_type == "SPY_HISTORY":
        return "spy_history"
    if "spotgamma_weekly" in source_file:
        return "processed_weekly"
    if source_type == "REVERSE_VRP":
        return "reverse_vrp"
    if source_type == "VRP":
        return "vrp"
    if source_type == "SQUEEZE":
        return "squeeze"
    return "processed_weekly"


def context_row_from_series(row: pd.Series) -> SpotGammaContextRow:
    def opt_float(col: str) -> float | None:
        if col not in row.index:
            return None
        return parse_numeric(row[col])

    def opt_str(col: str) -> str | None:
        if col not in row.index or pd.isna(row.get(col)):
            return None
        s = str(row[col]).strip()
        return s if s else None

    raw_input = opt_str("raw_input_date") if "raw_input_date" in row.index else None
    return SpotGammaContextRow(
        symbol=str(row["symbol"]).strip().upper(),
        trade_date=str(row["trade_date"]).strip(),
        source_file=str(row["source_file"]),
        source_type=str(row.get("source_type", "")).strip(),
        source_profile=_infer_source_profile(row),
        raw_input_date=raw_input,
        gamma_ratio=opt_float("gamma_ratio"),
        vrp=opt_float("vrp"),
        vrp_z=opt_float("vrp_z"),
        iv_rank=opt_float("iv_rank"),
        squeeze_score=opt_float("squeeze_score"),
        squeeze_state=opt_str("squeeze_state"),
        regime_label=opt_str("regime_label"),
        confidence=opt_float("confidence"),
        notes=str(row.get("notes", "") or ""),
        missing_fields=str(row.get("missing_fields", "") or ""),
    )


def load_contexts_from_csv(path: str | Path) -> list[SpotGammaContextRow]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"context csv not found: {p.resolve()}")
    df = pd.read_csv(p)
    return [context_row_from_series(row) for _, row in df.iterrows()]


def assess_context_csv_freshness(path: str | Path) -> ContextCsvFreshness:
    """
    A context CSV is fresh when it has ``source_profile`` and at least one raw profile row.

    Raw profiles: squeeze, vrp, reverse_vrp, spy_history (processed_weekly alone is not enough).
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"context csv not found: {p.resolve()}")
    header = pd.read_csv(p, nrows=0)
    if "source_profile" not in header.columns:
        return ContextCsvFreshness(
            is_fresh=False,
            has_source_profile_column=False,
            raw_profiles_found=frozenset(),
        )
    profiles = pd.read_csv(p, usecols=["source_profile"])["source_profile"].dropna().astype(str)
    found = frozenset({s.strip() for s in profiles.unique()} & _RAW_FRESH_PROFILES)
    return ContextCsvFreshness(
        is_fresh=bool(found),
        has_source_profile_column=True,
        raw_profiles_found=found,
    )


def rebuild_fresh_context(spotgamma_root: str | Path) -> list[SpotGammaContextRow]:
    """Rebuild context from committed ingest with raw profiles (paper-only, no execution)."""
    return build_context_corpus(spotgamma_root, include_raw=True)


def load_contexts(
    *,
    input_csv: Path | None,
    spotgamma_root: Path,
    include_raw: bool,
) -> list[SpotGammaContextRow]:
    if input_csv is not None and input_csv.is_file():
        return load_contexts_from_csv(input_csv)
    if include_raw or input_csv is None:
        return build_context_corpus(spotgamma_root, include_raw=True)
    raise FileNotFoundError(
        f"context input missing: {input_csv}; pass --include-raw to rebuild from {spotgamma_root}"
    )


def _spy_slice(ctx: SpotGammaContextRow) -> _SpyContextSlice:
    notes = parse_notes_kv(ctx.notes)
    return _SpyContextSlice(
        gamma_ratio=ctx.gamma_ratio,
        delta_ratio=_note_float(notes, "delta_ratio"),
        put_call_oi_ratio=_note_float(notes, "put_call_oi_ratio"),
        volume_ratio=_note_float(notes, "volume_ratio"),
        vrp=ctx.vrp,
        one_month_iv=_note_float(notes, "one_month_iv"),
        one_month_rv=_note_float(notes, "one_month_rv"),
        iv_rank=ctx.iv_rank,
        skew=_note_float(notes, "skew"),
        ne_skew=_note_float(notes, "ne_skew"),
        call_wall=_note_float(notes, "call_wall"),
        put_wall=_note_float(notes, "put_wall"),
        hedge_wall=_note_float(notes, "hedge_wall"),
    )


def build_spy_context_by_date(contexts: list[SpotGammaContextRow]) -> dict[str, _SpyContextSlice]:
    index: dict[str, _SpyContextSlice] = {}
    for ctx in contexts:
        if ctx.source_profile != "spy_history":
            continue
        if not ctx.trade_date:
            continue
        index[ctx.trade_date] = _spy_slice(ctx)
    return index


def _candidate_missing_fields(c: ReplayCandidateRow) -> list[str]:
    missing: list[str] = []
    for f in fields(ReplayCandidateRow):
        if f.name in {
            "symbol",
            "trade_date",
            "source_profile",
            "source_file",
            "candidate_reason",
            "missing_fields",
            "has_spy_context",
        }:
            continue
        if f.name.startswith("spy_") and not c.has_spy_context:
            missing.append(f.name)
            continue
        val = getattr(c, f.name)
        if val is None:
            missing.append(f.name)
    return missing


def _build_one_candidate(
    ctx: SpotGammaContextRow,
    spy_by_date: dict[str, _SpyContextSlice],
) -> ReplayCandidateRow | None:
    if ctx.source_profile not in _CANDIDATE_PROFILES:
        return None
    if ctx.source_profile == "spy_history":
        return None

    notes = parse_notes_kv(ctx.notes)
    base_reason = _REASON_BY_PROFILE.get(ctx.source_profile, "unknown_profile_candidate")
    spy = spy_by_date.get(ctx.trade_date)
    has_spy = spy is not None
    if has_spy:
        reason = f"{base_reason}+spy_context"
    else:
        reason = f"{base_reason}+missing_spy_context"

    options_impact = ctx.squeeze_score if ctx.squeeze_score is not None else _note_float(
        notes, "options_impact"
    )

    row = ReplayCandidateRow(
        symbol=ctx.symbol,
        trade_date=ctx.trade_date,
        source_profile=ctx.source_profile,
        source_file=ctx.source_file,
        current_price=_note_float(notes, "current_price"),
        gamma_ratio=ctx.gamma_ratio,
        delta_ratio=_note_float(notes, "delta_ratio"),
        put_call_oi_ratio=_note_float(notes, "put_call_oi_ratio"),
        volume_ratio=_note_float(notes, "volume_ratio"),
        iv_rank=ctx.iv_rank,
        vrp=ctx.vrp,
        one_month_iv=_note_float(notes, "one_month_iv"),
        one_month_rv=_note_float(notes, "one_month_rv"),
        skew=_note_float(notes, "skew"),
        ne_skew=_note_float(notes, "ne_skew"),
        options_impact=options_impact,
        options_implied_move=_note_float(notes, "options_implied_move"),
        call_wall=_note_float(notes, "call_wall"),
        put_wall=_note_float(notes, "put_wall"),
        hedge_wall=_note_float(notes, "hedge_wall"),
        spy_gamma_ratio=spy.gamma_ratio if spy else None,
        spy_delta_ratio=spy.delta_ratio if spy else None,
        spy_put_call_oi_ratio=spy.put_call_oi_ratio if spy else None,
        spy_volume_ratio=spy.volume_ratio if spy else None,
        spy_vrp=spy.vrp if spy else None,
        spy_one_month_iv=spy.one_month_iv if spy else None,
        spy_one_month_rv=spy.one_month_rv if spy else None,
        spy_iv_rank=spy.iv_rank if spy else None,
        spy_skew=spy.skew if spy else None,
        spy_ne_skew=spy.ne_skew if spy else None,
        spy_call_wall=spy.call_wall if spy else None,
        spy_put_wall=spy.put_wall if spy else None,
        spy_hedge_wall=spy.hedge_wall if spy else None,
        candidate_reason=reason,
        missing_fields="",
        has_spy_context=has_spy,
    )
    missing = _candidate_missing_fields(row)
    return ReplayCandidateRow(
        **{f.name: getattr(row, f.name) for f in fields(ReplayCandidateRow) if f.name != "missing_fields"},
        missing_fields=",".join(missing),
    )


def build_replay_candidates(contexts: list[SpotGammaContextRow]) -> list[ReplayCandidateRow]:
    spy_by_date = build_spy_context_by_date(contexts)
    out: list[ReplayCandidateRow] = []
    for ctx in contexts:
        cand = _build_one_candidate(ctx, spy_by_date)
        if cand is not None:
            out.append(cand)
    return out


def candidates_to_dataframe(candidates: list[ReplayCandidateRow]) -> pd.DataFrame:
    if not candidates:
        cols = [f.name for f in fields(ReplayCandidateRow)]
        return pd.DataFrame(columns=cols)
    return pd.DataFrame([{f.name: getattr(c, f.name) for f in fields(ReplayCandidateRow)} for c in candidates])


def summarize_replay_candidates(candidates: list[ReplayCandidateRow]) -> dict[str, object]:
    if not candidates:
        return {
            "row_count": 0,
            "symbol_count": 0,
            "date_min": "",
            "date_max": "",
            "by_source_profile": {},
            "with_spy_context": 0,
            "missing_spy_context": 0,
            "top_missing_fields": {},
        }
    dates = sorted({c.trade_date for c in candidates if c.trade_date})
    by_profile: dict[str, int] = {}
    missing_counts: dict[str, int] = {}
    with_spy = 0
    for c in candidates:
        by_profile[c.source_profile] = by_profile.get(c.source_profile, 0) + 1
        if c.has_spy_context:
            with_spy += 1
        for field in c.missing_fields.split(","):
            f = field.strip()
            if f:
                missing_counts[f] = missing_counts.get(f, 0) + 1
    top_missing = dict(
        sorted(missing_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:15]
    )
    return {
        "row_count": len(candidates),
        "symbol_count": len({c.symbol for c in candidates}),
        "date_min": dates[0] if dates else "",
        "date_max": dates[-1] if dates else "",
        "by_source_profile": dict(sorted(by_profile.items())),
        "with_spy_context": with_spy,
        "missing_spy_context": len(candidates) - with_spy,
        "top_missing_fields": top_missing,
    }
