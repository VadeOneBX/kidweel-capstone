"""Canonical evidence refresh across local staged CSVs (BT-C3); no transport or gate changes."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from qops.backtest.alpaca_greeks_layer import (
    HISTORICAL_REPLAY_MODE,
    PAPER_LIVE_MODE,
    PAPER_LIVE_PROVENANCE,
    PAPER_LIVE_ROW_SOURCE,
)
from qops.backtest.alpaca_replay_inputs import ReplayCandidateRow, load_replay_candidates_from_csv
from qops.backtest.replay_context import ReplayContext
from qops.risk.pmp_policy import min_rr_for_pmp
from qops.risk.paper_approval import SpreadCandidateInputRow, load_spread_candidate_rows
from qops.schemas.playbook import AllowedPlaybook
from qops.strategy.spread_candidate_generator import (
    GeneratedSpreadCandidate,
    generate_spread_candidates,
    load_greeks_quote_rows,
)
from qops.execution.paper_payload_candidate import PaperApprovalInputRow, load_paper_approval_rows

PROVENANCE_TAG = "bt_c3_canonical_refresh"

EvidenceClass = Literal[
    "PAPER_LIVE_EVIDENCE",
    "HISTORICAL_REPLAY_EVIDENCE",
    "STRUCTURE_EVIDENCE_ONLY",
    "FIXTURE_EVIDENCE",
    "INCOMPLETE_MISSING_DATA",
]

AdvisoryGroup = Literal[
    "SQUEEZE_CANDIDATES",
    "VOLATILITY_RISK_PREMIUM",
    "REVERSE_RISK_PREMIUM",
    "UNKNOWN",
]

_PROFILE_TO_ADVISORY: dict[str, AdvisoryGroup] = {
    "squeeze": "SQUEEZE_CANDIDATES",
    "vrp": "VOLATILITY_RISK_PREMIUM",
    "reverse_vrp": "REVERSE_RISK_PREMIUM",
}

_EXIT_PNL_COLUMNS = ("realized_pnl",)
_EXIT_PRICE_COLUMNS = ("exit_price", "exit_mid", "spread_exit_mid")


@dataclass(frozen=True, slots=True)
class CanonicalEvidenceRow:
    evidence_class: EvidenceClass
    advisory_group: AdvisoryGroup
    source_profile: str
    row_kind: str
    symbol: str
    trade_date: str
    structure_type: str
    long_leg_symbol: str
    short_leg_symbol: str
    expiration: str
    pmp: float | None
    pmp_source: str
    pmp_confidence: str
    reward_risk: float | None
    min_rr_required: float | None
    expected_value: float | None
    spread_delta: float | None
    candidate_pass: bool
    passes_spread_math_gate: bool
    pass_pmp_rr: bool
    pass_ev: bool
    failure_reasons: str
    realized_pnl: float | None
    pnl_source: str
    missing_exit: bool
    missing_pmp: bool
    provenance: str
    mode: str


@dataclass(frozen=True, slots=True)
class CanonicalRefreshPaths:
    spreads: Path
    approvals: Path
    payloads: Path
    greeks: Path
    sg: Path


def advisory_group_from_profile(source_profile: str) -> AdvisoryGroup:
    key = (source_profile or "").strip().lower()
    return _PROFILE_TO_ADVISORY.get(key, "UNKNOWN")


def _parse_float(raw: object) -> float | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    try:
        out = float(raw)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _parse_bool(raw: object) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return False
    return str(raw).strip().lower() in {"1", "true", "yes"}


def _expected_value(pmp: float, max_profit: float, max_loss: float) -> float:
    return pmp * max_profit - (1.0 - pmp) * max_loss


def _failure_has_rr_pmp_gap(reasons: str) -> bool:
    return "insufficient_reward_risk_for_probability" in (reasons or "")


def _pass_pmp_rr_from_reasons(
    *,
    reward_risk: float | None,
    min_rr: float | None,
    failure_reasons: str,
    passes_math: bool,
) -> bool:
    if _failure_has_rr_pmp_gap(failure_reasons):
        return False
    if reward_risk is not None and min_rr is not None and passes_math:
        return reward_risk >= min_rr
    return False


def _is_paper_live_metadata(*, mode: str, source: str, provenance: str) -> bool:
    m = (mode or "").strip().lower()
    s = (source or "").strip().lower()
    p = (provenance or "").strip().lower()
    if m == PAPER_LIVE_MODE:
        return True
    if s == PAPER_LIVE_ROW_SOURCE.lower():
        return True
    if PAPER_LIVE_PROVENANCE.lower() in p:
        return True
    return False


def _load_greeks_metadata_index(path: Path) -> tuple[dict[str, dict[str, str]], dict[tuple[str, str], str]]:
    """option_symbol -> {delta, mode, source, provenance, source_profile}; (symbol, date) -> profile."""
    by_option: dict[str, dict[str, str]] = {}
    by_sym_date: dict[tuple[str, str], str] = {}
    if not path.is_file():
        return by_option, by_sym_date
    df = pd.read_csv(path)
    for _, series in df.iterrows():
        opt = str(series.get("option_symbol", "")).strip()
        sym = str(series.get("underlying_symbol", "")).strip().upper()
        td = str(series.get("trade_date", "")).strip()
        profile = str(series.get("source_profile", "")).strip()
        if sym and td and profile:
            by_sym_date[(sym, td)] = profile
        if not opt:
            continue
        delta = _parse_float(series.get("delta"))
        by_option[opt] = {
            "delta": "" if delta is None else str(delta),
            "mode": str(series.get("mode", HISTORICAL_REPLAY_MODE)).strip(),
            "source": str(series.get("source", "")).strip(),
            "provenance": str(series.get("provenance", "")).strip(),
            "source_profile": profile,
        }
    return by_option, by_sym_date


def _spread_delta(
    long_sym: str,
    short_sym: str,
    structure_type: str,
    greeks_index: dict[str, dict[str, str]],
) -> float | None:
    long_meta = greeks_index.get(long_sym.strip())
    short_meta = greeks_index.get(short_sym.strip())
    if not long_meta or not short_meta:
        return None
    ld = _parse_float(long_meta.get("delta"))
    sd = _parse_float(short_meta.get("delta"))
    if ld is None or sd is None:
        return None
    if structure_type in {
        AllowedPlaybook.BULL_CALL_SPREAD.value,
        AllowedPlaybook.BEAR_PUT_SPREAD.value,
    }:
        return ld - sd
    return sd - ld


def _historical_exit_from_series(series: pd.Series) -> tuple[float | None, bool, str]:
    for col in _EXIT_PNL_COLUMNS:
        if col in series.index:
            pnl = _parse_float(series.get(col))
            if pnl is not None:
                return pnl, False, f"declared_{col}"
    has_exit_price = any(
        col in series.index and _parse_float(series.get(col)) is not None for col in _EXIT_PRICE_COLUMNS
    )
    if has_exit_price:
        return None, False, "exit_price_present_no_pnl"
    return None, True, ""


def _evidence_class_for_structure(
    *,
    paper_live: bool,
    realized_pnl: float | None,
    has_exit_price_only: bool,
) -> EvidenceClass:
    if paper_live:
        return "PAPER_LIVE_EVIDENCE"
    if realized_pnl is not None:
        return "HISTORICAL_REPLAY_EVIDENCE"
    if has_exit_price_only:
        return "HISTORICAL_REPLAY_EVIDENCE"
    return "STRUCTURE_EVIDENCE_ONLY"


def _generated_to_input_row(c: GeneratedSpreadCandidate) -> SpreadCandidateInputRow:
    return SpreadCandidateInputRow(
        structure_type=c.structure_type,
        underlying_symbol=c.underlying_symbol,
        trade_date=c.trade_date,
        expiration=c.expiration,
        long_option_symbol=c.long_option_symbol,
        short_option_symbol=c.short_option_symbol,
        spread_width=c.spread_width,
        net_debit_or_credit=c.net_debit_or_credit,
        pmp_for_gate=c.pmp_for_gate,
        pmp_source=c.pmp_source,
        pmp_confidence=c.pmp_confidence,
        max_profit=c.math.max_profit,
        max_loss=c.math.max_loss,
        reward_risk=c.math.reward_risk,
        break_even=c.math.break_even,
        capital_at_risk=c.math.capital_at_risk,
        passes_spread_math_gate=c.math.passes_spread_math_gate,
        probability_status=c.math.probability_status,
        ev_status=c.math.ev_status,
        candidate_pass=c.candidate_pass,
        failure_reasons="|".join(c.failure_reasons),
        provenance=c.provenance,
    )


def _resolve_spread_rows(
    spreads_path: Path,
    greeks_path: Path,
    *,
    derive_if_missing: bool,
    limit: int | None,
) -> tuple[list[SpreadCandidateInputRow], bool]:
    rows = load_spread_candidate_rows(spreads_path)
    if rows:
        if limit is not None and limit > 0:
            rows = rows[:limit]
        return rows, False
    if not derive_if_missing:
        return [], False
    staged = load_greeks_quote_rows(greeks_path)
    if not staged:
        return [], False
    generated = generate_spread_candidates(staged, limit=limit)
    return [_generated_to_input_row(c) for c in generated], True


def _enrich_spread_row(
    row: SpreadCandidateInputRow,
    *,
    greeks_index: dict[str, dict[str, str]],
    sym_date_profile: dict[tuple[str, str], str],
    extra_series: pd.Series | None,
) -> CanonicalEvidenceRow:
    sym = row.underlying_symbol.strip().upper()
    td = row.trade_date.strip()
    profile = sym_date_profile.get((sym, td), "")
    long_meta = greeks_index.get(row.long_option_symbol.strip(), {})
    short_meta = greeks_index.get(row.short_option_symbol.strip(), {})
    if not profile:
        profile = long_meta.get("source_profile") or short_meta.get("source_profile") or ""

    mode = long_meta.get("mode") or short_meta.get("mode") or HISTORICAL_REPLAY_MODE
    source = long_meta.get("source") or short_meta.get("source") or ""
    provenance = row.provenance or long_meta.get("provenance") or short_meta.get("provenance") or ""
    paper_live = _is_paper_live_metadata(mode=mode, source=source, provenance=provenance)

    realized_pnl: float | None = None
    pnl_source = ""
    missing_exit = True
    has_exit_price_only = False
    if extra_series is not None:
        realized_pnl, missing_exit, pnl_source = _historical_exit_from_series(extra_series)
        if pnl_source == "exit_price_present_no_pnl":
            has_exit_price_only = True
            missing_exit = False
    else:
        missing_exit = True

    pmp = row.pmp_for_gate
    missing_pmp = pmp is None
    min_rr: float | None = None
    ev: float | None = None
    if pmp is not None:
        try:
            min_rr = min_rr_for_pmp(pmp)
        except ValueError:
            min_rr = None
        if row.max_profit is not None and row.max_loss is not None:
            ev = _expected_value(pmp, row.max_profit, row.max_loss)

    pass_ev = row.ev_status == "PASS"
    pass_pmp_rr = _pass_pmp_rr_from_reasons(
        reward_risk=row.reward_risk,
        min_rr=min_rr,
        failure_reasons=row.failure_reasons,
        passes_math=row.passes_spread_math_gate,
    )

    evidence_class = _evidence_class_for_structure(
        paper_live=paper_live,
        realized_pnl=realized_pnl,
        has_exit_price_only=has_exit_price_only,
    )

    return CanonicalEvidenceRow(
        evidence_class=evidence_class,
        advisory_group=advisory_group_from_profile(profile),
        source_profile=profile,
        row_kind="spread_candidate",
        symbol=sym,
        trade_date=td,
        structure_type=row.structure_type,
        long_leg_symbol=row.long_option_symbol,
        short_leg_symbol=row.short_option_symbol,
        expiration=row.expiration,
        pmp=pmp,
        pmp_source=row.pmp_source,
        pmp_confidence=row.pmp_confidence,
        reward_risk=row.reward_risk,
        min_rr_required=min_rr,
        expected_value=ev,
        spread_delta=_spread_delta(
            row.long_option_symbol,
            row.short_option_symbol,
            row.structure_type,
            greeks_index,
        ),
        candidate_pass=row.candidate_pass,
        passes_spread_math_gate=row.passes_spread_math_gate,
        pass_pmp_rr=pass_pmp_rr,
        pass_ev=pass_ev,
        failure_reasons=row.failure_reasons,
        realized_pnl=realized_pnl,
        pnl_source=pnl_source,
        missing_exit=missing_exit,
        missing_pmp=missing_pmp,
        provenance=provenance or PROVENANCE_TAG,
        mode=mode,
    )


def evidence_rows_from_sg_replay(rows: list[ReplayCandidateRow]) -> list[CanonicalEvidenceRow]:
    out: list[CanonicalEvidenceRow] = []
    for r in rows:
        out.append(
            CanonicalEvidenceRow(
                evidence_class="INCOMPLETE_MISSING_DATA",
                advisory_group=advisory_group_from_profile(r.source_profile),
                source_profile=r.source_profile,
                row_kind="spotgamma_replay_context",
                symbol=r.symbol.strip().upper(),
                trade_date=r.trade_date.strip(),
                structure_type="",
                long_leg_symbol="",
                short_leg_symbol="",
                expiration="",
                pmp=None,
                pmp_source="missing",
                pmp_confidence="MISSING",
                reward_risk=None,
                min_rr_required=None,
                expected_value=None,
                spread_delta=None,
                candidate_pass=False,
                passes_spread_math_gate=False,
                pass_pmp_rr=False,
                pass_ev=False,
                failure_reasons=r.missing_fields or "context_only_no_spread_economics",
                realized_pnl=None,
                pnl_source="",
                missing_exit=True,
                missing_pmp=True,
                provenance="spotgamma_replay_builder",
                mode=HISTORICAL_REPLAY_MODE,
            )
        )
    return out


def evidence_rows_from_fixtures(
    tagged: list[tuple[str, ReplayContext]],
) -> list[CanonicalEvidenceRow]:
    out: list[CanonicalEvidenceRow] = []
    for source, ctx in tagged:
        ev = ctx.evaluation
        pmp = ev.pmp
        min_rr: float | None = None
        if pmp is not None:
            try:
                min_rr = min_rr_for_pmp(pmp)
            except ValueError:
                min_rr = None
        out.append(
            CanonicalEvidenceRow(
                evidence_class="FIXTURE_EVIDENCE",
                advisory_group="UNKNOWN",
                source_profile="",
                row_kind="replay_context_fixture",
                symbol=ctx.symbol.strip().upper(),
                trade_date=ctx.entry_date.strip(),
                structure_type=ctx.playbook,
                long_leg_symbol="",
                short_leg_symbol="",
                expiration=ctx.structure.expiry,
                pmp=pmp,
                pmp_source="fixture_declared",
                pmp_confidence="MISSING",
                reward_risk=ev.rr_actual,
                min_rr_required=min_rr,
                expected_value=None,
                spread_delta=None,
                candidate_pass=ev.approved,
                passes_spread_math_gate=ev.pass_rr,
                pass_pmp_rr=ev.pass_rr,
                pass_ev=False,
                failure_reasons=f"fixture_source={source}",
                realized_pnl=ctx.realized_pnl,
                pnl_source="fixture_declared",
                missing_exit=False,
                missing_pmp=pmp is None,
                provenance=f"bt_c1_fixture|{source}",
                mode=HISTORICAL_REPLAY_MODE,
            )
        )
    return out


def _count_payload_ready(path: Path) -> int:
    if not path.is_file():
        return 0
    df = pd.read_csv(path)
    if "payload_status" not in df.columns:
        return 0
    return int((df["payload_status"].astype(str).str.strip() == "PAPER_PAYLOAD_READY").sum())


def _finite_mean(values: list[float | None]) -> float | None:
    nums = [v for v in values if v is not None and math.isfinite(v)]
    if not nums:
        return None
    return sum(nums) / len(nums)


def _rank_top(
    rows: list[CanonicalEvidenceRow],
    *,
    structure_filter: str | None,
    key_fn,
    limit: int = 10,
) -> list[dict[str, Any]]:
    pool = rows
    if structure_filter:
        pool = [r for r in pool if r.structure_type == structure_filter]
    ranked = sorted(pool, key=key_fn, reverse=True)
    out: list[dict[str, Any]] = []
    for r in ranked[:limit]:
        out.append(
            {
                "symbol": r.symbol,
                "trade_date": r.trade_date,
                "structure_type": r.structure_type,
                "advisory_group": r.advisory_group,
                "reward_risk": r.reward_risk,
                "pmp": r.pmp,
                "spread_delta": r.spread_delta,
                "candidate_pass": r.candidate_pass,
            }
        )
    return out


def summarize_canonical_refresh(
    *,
    all_rows: list[CanonicalEvidenceRow],
    spread_input_count: int,
    spread_derived: bool,
    approval_rows: list[PaperApprovalInputRow],
    payload_ready_count: int,
    inputs_present: dict[str, bool],
    limitations: list[str],
) -> dict[str, Any]:
    structure_rows = [r for r in all_rows if r.row_kind == "spread_candidate"]
    by_class: dict[str, int] = {}
    for r in all_rows:
        by_class[r.evidence_class] = by_class.get(r.evidence_class, 0) + 1

    math_pass = sum(1 for r in structure_rows if r.passes_spread_math_gate)
    pmp_rr_pass = sum(1 for r in structure_rows if r.pass_pmp_rr)
    ev_pass = sum(1 for r in structure_rows if r.pass_ev)
    candidate_pass = sum(1 for r in structure_rows if r.candidate_pass)
    approval_ready = sum(1 for a in approval_rows if a.approval_status == "APPROVED_FOR_PAPER_REVIEW")

    hist_pnl = [
        r
        for r in all_rows
        if r.evidence_class == "HISTORICAL_REPLAY_EVIDENCE"
        and r.realized_pnl is not None
        and r.pnl_source.startswith("declared_")
    ]

    advisory_counts: dict[str, int] = {}
    advisory_pass: dict[str, list[bool]] = {}
    for r in structure_rows:
        g = r.advisory_group
        advisory_counts[g] = advisory_counts.get(g, 0) + 1
        advisory_pass.setdefault(g, []).append(r.candidate_pass)
    advisory_pass_rates = {
        g: (sum(1 for p in ps if p) / len(ps) if ps else 0.0) for g, ps in advisory_pass.items()
    }

    rr_pmp_fail = sum(1 for r in structure_rows if _failure_has_rr_pmp_gap(r.failure_reasons))

    squeeze_rows = [
        r
        for r in structure_rows
        if r.advisory_group == "SQUEEZE_CANDIDATES" and r.spread_delta is not None
    ]

    return {
        "provenance": PROVENANCE_TAG,
        "total_rows_inspected": len(all_rows),
        "spread_input_rows": spread_input_count,
        "spread_rows_derived_in_memory": spread_derived,
        "candidates_generated": len(structure_rows),
        "candidates_passing_math": math_pass,
        "candidates_passing_pmp_rr": pmp_rr_pass,
        "candidates_passing_ev": ev_pass,
        "candidate_pass_count": candidate_pass,
        "approval_ready_count": approval_ready,
        "payload_ready_count": payload_ready_count,
        "evidence_rows_by_class": by_class,
        "structure_only_rows": by_class.get("STRUCTURE_EVIDENCE_ONLY", 0),
        "trades_with_real_exit_pnl": len(hist_pnl),
        "missing_pmp_count": sum(1 for r in structure_rows if r.missing_pmp),
        "missing_exit_count": sum(1 for r in structure_rows if r.missing_exit),
        "average_reward_risk": _finite_mean([r.reward_risk for r in structure_rows]),
        "average_min_rr_required": _finite_mean([r.min_rr_required for r in structure_rows]),
        "average_pmp": _finite_mean([r.pmp for r in structure_rows]),
        "average_spread_delta": _finite_mean([r.spread_delta for r in structure_rows]),
        "advisory_group_counts": advisory_counts,
        "advisory_group_pass_rates": advisory_pass_rates,
        "top_candidates_by_rr_pmp": _rank_top(
            structure_rows,
            structure_filter=AllowedPlaybook.BULL_CALL_SPREAD.value,
            key_fn=lambda r: (r.reward_risk or -1.0, r.pmp or -1.0),
        ),
        "top_squeeze_candidates_by_spread_delta": _rank_top(
            squeeze_rows,
            structure_filter=None,
            key_fn=lambda r: r.spread_delta or -1.0,
        ),
        "rr_pmp_summary": {
            "insufficient_reward_risk_for_pmp_count": rr_pmp_fail,
            "average_reward_risk": _finite_mean([r.reward_risk for r in structure_rows]),
            "average_pmp": _finite_mean([r.pmp for r in structure_rows]),
            "average_min_rr_required": _finite_mean([r.min_rr_required for r in structure_rows]),
            "pmp_rr_pass_count": pmp_rr_pass,
            "candidate_pass_count": candidate_pass,
        },
        "missing_data_summary": {
            "missing_pmp_count": sum(1 for r in structure_rows if r.missing_pmp),
            "missing_exit_count": sum(1 for r in structure_rows if r.missing_exit),
            "missing_spread_delta_count": sum(
                1 for r in structure_rows if r.spread_delta is None
            ),
            "incomplete_context_rows": by_class.get("INCOMPLETE_MISSING_DATA", 0),
        },
        "per_class_summaries": _per_class_summaries(all_rows),
        "inputs_present": inputs_present,
        "limitations": limitations,
    }


def _per_class_summaries(rows: list[CanonicalEvidenceRow]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    classes = sorted({r.evidence_class for r in rows})
    for cls in classes:
        subset = [r for r in rows if r.evidence_class == cls]
        out[cls] = {
            "row_count": len(subset),
            "candidate_pass_count": sum(1 for r in subset if r.candidate_pass),
            "average_reward_risk": _finite_mean([r.reward_risk for r in subset]),
            "average_pmp": _finite_mean([r.pmp for r in subset]),
            "realized_pnl_count": sum(1 for r in subset if r.realized_pnl is not None),
        }
    return out


def run_canonical_backtest_refresh(
    paths: CanonicalRefreshPaths,
    *,
    derive_spreads_if_missing: bool = True,
    limit: int | None = None,
    fixture_tagged: list[tuple[str, ReplayContext]] | None = None,
) -> tuple[list[CanonicalEvidenceRow], dict[str, Any]]:
    inputs_present = {
        "spreads": paths.spreads.is_file(),
        "approvals": paths.approvals.is_file(),
        "payloads": paths.payloads.is_file(),
        "greeks": paths.greeks.is_file(),
        "sg": paths.sg.is_file(),
    }
    limitations: list[str] = []
    if not any(inputs_present.values()) and not fixture_tagged:
        limitations.append("no_input_csvs_or_fixtures_present")

    greeks_index, sym_date_profile = _load_greeks_metadata_index(paths.greeks)
    spread_rows, derived = _resolve_spread_rows(
        paths.spreads,
        paths.greeks,
        derive_if_missing=derive_spreads_if_missing,
        limit=limit,
    )
    if derived:
        limitations.append("spread_candidates_derived_in_memory_from_greeks")

    spread_df = pd.read_csv(paths.spreads) if paths.spreads.is_file() else None
    evidence: list[CanonicalEvidenceRow] = []
    for i, row in enumerate(spread_rows):
        extra = None
        if spread_df is not None and i < len(spread_df):
            extra = spread_df.iloc[i]
        evidence.append(
            _enrich_spread_row(
                row,
                greeks_index=greeks_index,
                sym_date_profile=sym_date_profile,
                extra_series=extra,
            )
        )

    sg_rows: list[ReplayCandidateRow] = []
    if paths.sg.is_file():
        sg_rows = load_replay_candidates_from_csv(paths.sg)
        if limit is not None and limit > 0:
            sg_rows = sg_rows[:limit]
    evidence.extend(evidence_rows_from_sg_replay(sg_rows))

    if fixture_tagged:
        evidence.extend(evidence_rows_from_fixtures(fixture_tagged))

    approval_rows = load_paper_approval_rows(paths.approvals)
    if limit is not None and limit > 0:
        approval_rows = approval_rows[:limit]
    payload_ready = _count_payload_ready(paths.payloads)

    summary = summarize_canonical_refresh(
        all_rows=evidence,
        spread_input_count=len(spread_rows),
        spread_derived=derived,
        approval_rows=approval_rows,
        payload_ready_count=payload_ready,
        inputs_present=inputs_present,
        limitations=limitations,
    )
    return evidence, summary


def evidence_rows_to_dataframe(rows: list[CanonicalEvidenceRow]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=[f.name for f in fields(CanonicalEvidenceRow)])
    return pd.DataFrame([asdict(r) for r in rows])


def summary_to_json(summary: dict[str, Any]) -> str:
    return json.dumps(summary, indent=2, sort_keys=True)
