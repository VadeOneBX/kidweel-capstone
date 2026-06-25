from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from pydantic import BaseModel

from qops.advisory.am_note_gate import (
    apply_am_note_paper_gate_to_audit,
    build_macro_paper_gate,
)
from qops.advisory.expression_frontier import (
    apply_frontier_paper_gate_to_audit,
    build_expression_frontier,
)
from qops.playbooks.selector import select_allowed_playbook
from qops.risk.paper_approval import (
    build_paper_approval_candidates,
    load_spread_candidate_rows,
    paper_approval_to_dataframe,
)
from qops.runtime.execution_halt import assert_not_halted
from qops.schemas.environment import (
    DirectionalBias,
    EnvironmentSnapshot,
    HostageState,
    IVState,
    RegimeLabel,
    SkewState,
    WallState,
)
from qops.pipeline.alpaca_hydration_loop import C2A_EVIDENCE_COLUMNS
from qops.schemas.candidate_loop import CandidateLoopStatus, HydrationStatus
from qops.schemas.playbook import AllowedPlaybook, StructureBias

PROVENANCE_TAG = "guard_c1f_morning_risk_audit"

GuardClassification = str

_VRP_SCANNER_PROFILES = frozenset({"vrp", "reverse_vrp"})

_CONTEXT_GATE_PASS = "CONTEXT_PASS"
_CONTEXT_GATE_BLOCKED = "CONTEXT_BLOCKED"
_CONTEXT_GATE_INCOMPLETE = "CONTEXT_INCOMPLETE"

_SPREAD_CONTRACT_COLUMNS = (
    "structure",
    "expiration",
    "dte",
    "long_leg_symbol",
    "short_leg_symbol",
    "long_strike",
    "short_strike",
    "debit",
    "credit",
    "width",
    "max_profit",
    "max_loss",
    "rr_actual",
    "pmp",
    "ev",
)

_RISK_AUDIT_COLUMNS = (
    "run_id",
    "symbol",
    "underlying",
    "regime_label",
    "structure_bias",
    "playbook",
    "structure",
    "expiration",
    "dte",
    "long_leg_symbol",
    "short_leg_symbol",
    "long_strike",
    "short_strike",
    "debit",
    "credit",
    "width",
    "max_profit",
    "max_loss",
    "rr_actual",
    "pmp",
    "ev",
    "liquidity_status",
    "paper_approval_status",
    "reject_reason",
    "gamma_ratio_source",
    "classification",
    "provenance",
) + C2A_EVIDENCE_COLUMNS


class RiskGuardResult(BaseModel):
    risk_audit_artifact: str


def _empty_cell(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def spread_contract_gaps(row: pd.Series) -> list[str]:
    missing: list[str] = []
    for col in _SPREAD_CONTRACT_COLUMNS:
        if col not in row.index or _empty_cell(row.get(col)):
            missing.append(col)
    return missing


def enrich_morning_candidate_export(df: pd.DataFrame, *, run_id: str) -> pd.DataFrame:
    """Add risk-guard contract columns to replay candidate exports (spread fields blank)."""
    if df.empty:
        out = pd.DataFrame(columns=list(_RISK_AUDIT_COLUMNS))
        return out

    out = df.copy()
    out.insert(0, "run_id", run_id)
    out["underlying"] = out.get("symbol", pd.Series(dtype=str)).astype(str).str.upper()
    out["regime_label"] = ""
    out["structure_bias"] = StructureBias.SKIP.value
    out["playbook"] = AllowedPlaybook.SKIP.value
    for col in _SPREAD_CONTRACT_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    out["liquidity_status"] = "UNKNOWN"
    out["paper_approval_status"] = ""
    out["reject_reason"] = ""
    if "gamma_ratio_source" not in out.columns:
        out["gamma_ratio_source"] = ""
    for col in C2A_EVIDENCE_COLUMNS:
        if col not in out.columns:
            out[col] = ""
        if col == "candidate_loop_status":
            out[col] = CandidateLoopStatus.HYDRATION_PENDING.value
        elif col == "hydration_status":
            out[col] = HydrationStatus.REQUERY_REQUIRED.value
        elif col in ("expression_count", "alternate_expression_count"):
            out[col] = 0
        elif col in (
            "rr_baseline_required",
            "rr_dealer_required",
            "pmp_baseline_max",
            "pmp_dealer_max",
        ):
            out[col] = ""
        elif col in ("context_gate_status", "context_gate_reason"):
            out[col] = ""
        elif col in ("primary_expression_id", "watch_expression_id"):
            out[col] = ""
    return out


def _context_gate_labels(
    *,
    profile: str,
    missing_fields: str,
    has_spy_context: bool,
) -> tuple[str, str]:
    gaps = [
        part.strip()
        for part in missing_fields.split(",")
        if part.strip() and part.strip().lower() != "nan"
    ]
    if profile == "reverse_vrp":
        gaps = [g for g in gaps if g != "spy_context"]
    if gaps:
        return _CONTEXT_GATE_INCOMPLETE, ",".join(gaps)
    if profile == "reverse_vrp" and not has_spy_context:
        return _CONTEXT_GATE_PASS, "missing_spy_context"
    return _CONTEXT_GATE_PASS, ""


def hydrate_morning_replay_candidates(
    df: pd.DataFrame,
    context_df: pd.DataFrame,
) -> pd.DataFrame:
    """C1f slice 1: SPY backdrop regime + squeeze→VRP gamma join (no SPX→single-name inference)."""
    if df.empty:
        return df

    out = df.copy()
    regime_by_date: dict[str, str] = {}
    for trade_date in out.get("trade_date", pd.Series(dtype=str)).dropna().unique():
        td = str(trade_date).strip()
        label = _spy_regime_label(context_df, td)
        if label:
            regime_by_date[td] = label

    squeeze_gamma: dict[str, float] = {}
    if "source_profile" in out.columns and "symbol" in out.columns:
        squeeze_mask = out["source_profile"].astype(str) == "squeeze"
        for _, squeeze_row in out.loc[squeeze_mask].iterrows():
            gamma = squeeze_row.get("gamma_ratio")
            if gamma is None or pd.isna(gamma):
                continue
            sym = str(squeeze_row.get("symbol", "")).strip().upper()
            if sym:
                squeeze_gamma[sym] = float(gamma)

    gamma_values: list[object] = []
    sources: list[str] = []
    regimes: list[str] = []
    missing_fields: list[str] = []
    gate_statuses: list[str] = []
    gate_reasons: list[str] = []

    for _, row in out.iterrows():
        symbol = str(row.get("symbol", "")).strip().upper()
        profile = str(row.get("source_profile", "")).strip()
        trade_date = str(row.get("trade_date", "")).strip()
        gamma = row.get("gamma_ratio")

        if profile == "squeeze":
            if gamma is not None and not pd.isna(gamma):
                source = "squeeze"
            else:
                source = "source_absent"
        elif profile in _VRP_SCANNER_PROFILES:
            if symbol in squeeze_gamma:
                gamma = squeeze_gamma[symbol]
                source = "squeeze_join"
            else:
                source = "source_absent"
        elif gamma is not None and not pd.isna(gamma):
            source = "squeeze"
        else:
            source = ""

        missing: list[str] = []
        if profile != "reverse_vrp" and not bool(row.get("has_spy_context")):
            missing.append("spy_context")
        if profile not in _VRP_SCANNER_PROFILES and source != "source_absent" and (
            gamma is None or pd.isna(gamma)
        ):
            missing.append("gamma_ratio")

        gate_status, gate_reason = _context_gate_labels(
            profile=profile,
            missing_fields=",".join(missing),
            has_spy_context=bool(row.get("has_spy_context")),
        )

        gamma_values.append(gamma)
        sources.append(source)
        regimes.append(regime_by_date.get(trade_date, str(row.get("regime_label", "") or "").strip()))
        missing_fields.append(",".join(missing))
        gate_statuses.append(gate_status)
        gate_reasons.append(gate_reason)

    out["gamma_ratio"] = gamma_values
    out["gamma_ratio_source"] = sources
    out["regime_label"] = regimes
    out["missing_fields"] = missing_fields
    out["context_gate_status"] = gate_statuses
    out["context_gate_reason"] = gate_reasons
    return out


def _spy_regime_label(context_df: pd.DataFrame, trade_date: str) -> str | None:
    if context_df.empty or not trade_date:
        return None
    mask = (context_df["symbol"] == "SPY") & (context_df["trade_date"] == trade_date)
    spy = context_df.loc[mask]
    if spy.empty:
        mask = context_df["symbol"] == "SPY"
        spy = context_df.loc[mask]
    if spy.empty:
        return None
    val = spy.iloc[-1].get("regime_label")
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    text = str(val).strip()
    return text or None


def _playbook_decision_for_row(row: pd.Series):
    symbol = str(row.get("symbol", "")).strip().upper() or "UNKNOWN"
    gamma = row.get("gamma_ratio")
    gamma_ratio = float(gamma) if gamma is not None and pd.notna(gamma) else None
    env = EnvironmentSnapshot(
        symbol=symbol,
        regime_label=RegimeLabel.NEUTRAL,
        confidence=0,
        gamma_ratio=gamma_ratio,
        iv_state=IVState.MID_VOL,
        skew_state=SkewState.NEUTRAL,
        wall_state=WallState.UNKNOWN,
        directional_bias=DirectionalBias.NEUTRAL_BIAS,
        hostage_state=HostageState.UNKNOWN,
        environment_label="morning_replay_staging",
        environment_reason="replay_candidate_not_screened",
    )
    structure_bias = StructureBias.SKIP
    return select_allowed_playbook(symbol, structure_bias, env)


def _map_approval_failure_to_classification(reason: str, failure_reasons: str) -> GuardClassification:
    blob = f"{reason}|{failure_reasons}".lower()
    if any(k in blob for k in ("insufficient_reward_risk", "reward_risk", "spread_math_gate")):
        return "REJECTED_RR"
    if any(k in blob for k in ("missing_pmp", "pmp_outside", "probability_gate", "ev_gate")):
        return "REJECTED_PMP"
    if any(k in blob for k in ("liquidity", "bid", "ask")):
        return "REJECTED_LIQUIDITY"
    if "incomplete" in blob or "missing_" in blob:
        return "REJECTED_MISSING_FIELDS"
    return "REJECTED_POLICY"


@dataclass(frozen=True, slots=True)
class _ReplayAudit:
    classification: GuardClassification
    reject_reason: str
    structure_bias: str
    playbook: str
    regime_label: str
    spread_gaps: list[str]
    context_gaps: list[str]


def _classify_replay_candidate(
    row: pd.Series,
    *,
    spy_regime_label: str | None,
) -> _ReplayAudit:
    symbol = str(row.get("symbol", "")).strip().upper()
    trade_date = str(row.get("trade_date", "")).strip()
    context_gaps = [
        part.strip()
        for part in str(row.get("missing_fields", "") or "").split(",")
        if part.strip() and part.strip().lower() != "nan"
    ]
    profile = str(row.get("source_profile", "") or "").strip()
    if profile == "reverse_vrp":
        context_gaps = [g for g in context_gaps if g != "spy_context"]
    gamma_source = str(row.get("gamma_ratio_source", "") or "").strip()
    if gamma_source == "source_absent":
        context_gaps = [gap for gap in context_gaps if gap != "gamma_ratio"]
    spread_gaps = spread_contract_gaps(row)
    has_spy = bool(row.get("has_spy_context"))

    gate_status = str(row.get("context_gate_status", "") or "").strip()
    gate_reason = str(row.get("context_gate_reason", "") or "").strip()
    if not gate_status:
        gate_status, gate_reason = _context_gate_labels(
            profile=profile,
            missing_fields=",".join(context_gaps),
            has_spy_context=has_spy,
        )

    playbook_decision = _playbook_decision_for_row(row)
    allowed = playbook_decision.allowed_playbook
    structure_bias = StructureBias.SKIP.value
    regime = str(row.get("regime_label", "") or "").strip() or (spy_regime_label or "")

    if not symbol:
        return _ReplayAudit(
            _CONTEXT_GATE_BLOCKED,
            "context_gate:missing_symbol",
            structure_bias,
            allowed.value,
            regime,
            spread_gaps,
            ["missing_symbol"],
        )
    if not trade_date:
        return _ReplayAudit(
            _CONTEXT_GATE_BLOCKED,
            "context_gate:missing_trade_date",
            structure_bias,
            allowed.value,
            regime,
            spread_gaps,
            ["missing_trade_date"],
        )
    if gate_status == _CONTEXT_GATE_BLOCKED:
        return _ReplayAudit(
            _CONTEXT_GATE_BLOCKED,
            f"context_gate:{gate_reason or 'blocked'}",
            structure_bias,
            allowed.value,
            regime,
            spread_gaps,
            context_gaps,
        )
    if gate_status == _CONTEXT_GATE_INCOMPLETE or context_gaps:
        gaps = context_gaps or [gate_reason]
        return _ReplayAudit(
            _CONTEXT_GATE_INCOMPLETE,
            "context_gate:" + ",".join(g for g in gaps if g),
            structure_bias,
            allowed.value,
            regime,
            spread_gaps,
            gaps,
        )
    if spread_gaps:
        loop_status = str(row.get("candidate_loop_status", "") or "").strip()
        data_gap = str(row.get("data_gap_reason", "") or "").strip()
        hydration = str(row.get("hydration_status", "") or "").strip()
        if loop_status == CandidateLoopStatus.NO_VIABLE_EXPRESSION.value:
            return _ReplayAudit(
                CandidateLoopStatus.NO_VIABLE_EXPRESSION.value,
                "expression_search_exhausted:no_viable_expression",
                structure_bias,
                allowed.value,
                regime,
                spread_gaps,
                [],
            )
        if loop_status == CandidateLoopStatus.PARKED_DATA_GAP.value:
            reason = data_gap or "candidate retained; Alpaca quote hydration incomplete"
            return _ReplayAudit(
                CandidateLoopStatus.PARKED_DATA_GAP.value,
                reason,
                structure_bias,
                allowed.value,
                regime,
                spread_gaps,
                [],
            )
        if loop_status in {
            CandidateLoopStatus.PRIMARY_EXPRESSION_SELECTED.value,
            CandidateLoopStatus.ALTERNATES_AVAILABLE.value,
            CandidateLoopStatus.WATCH_EXPRESSION_AVAILABLE.value,
            CandidateLoopStatus.HYDRATED.value,
        }:
            return _ReplayAudit(
                loop_status,
                str(row.get("selection_reason", "") or "primary_expression_selected"),
                structure_bias,
                allowed.value,
                regime,
                [],
                [],
            )
        pending_reason = (
            f"expression_hydration_pending:{hydration or 'spread_economics_incomplete'}"
        )
        return _ReplayAudit(
            CandidateLoopStatus.HYDRATION_PENDING.value,
            pending_reason,
            structure_bias,
            allowed.value,
            regime,
            spread_gaps,
            [],
        )
    loop_status = str(row.get("candidate_loop_status", "") or "").strip()
    if loop_status in {
        CandidateLoopStatus.PRIMARY_EXPRESSION_SELECTED.value,
        CandidateLoopStatus.ALTERNATES_AVAILABLE.value,
        CandidateLoopStatus.WATCH_EXPRESSION_AVAILABLE.value,
        CandidateLoopStatus.HYDRATED.value,
    }:
        return _ReplayAudit(
            loop_status,
            str(row.get("selection_reason", "") or "primary_expression_selected"),
            structure_bias,
            allowed.value,
            regime,
            [],
            [],
        )
    if allowed == AllowedPlaybook.SKIP:
        return _ReplayAudit(
            "PARKED_REVIEW",
            playbook_decision.decision_reason or "structure_resolves_to_skip",
            structure_bias,
            allowed.value,
            regime,
            [],
            [],
        )
    if not has_spy and profile != "reverse_vrp":
        return _ReplayAudit(
            "PARKED_REVIEW",
            "missing_spy_context",
            structure_bias,
            allowed.value,
            regime,
            [],
            [],
        )
    return _ReplayAudit(
        "PARKED_REVIEW",
        "replay_staging_awaiting_spread_math",
        structure_bias,
        allowed.value,
        regime,
        [],
        [],
    )


def _audit_row_from_series(
    row: pd.Series,
    *,
    run_id: str,
    audited: _ReplayAudit,
) -> dict[str, object]:
    symbol = str(row.get("symbol", "")).strip().upper()
    payload: dict[str, object] = {
        "run_id": run_id,
        "symbol": symbol,
        "underlying": symbol,
        "regime_label": audited.regime_label,
        "structure_bias": audited.structure_bias,
        "playbook": audited.playbook,
        "structure": row.get("structure", ""),
        "expiration": row.get("expiration", ""),
        "dte": row.get("dte", ""),
        "long_leg_symbol": row.get("long_leg_symbol", ""),
        "short_leg_symbol": row.get("short_leg_symbol", ""),
        "long_strike": row.get("long_strike", ""),
        "short_strike": row.get("short_strike", ""),
        "debit": row.get("debit", ""),
        "credit": row.get("credit", ""),
        "width": row.get("width", ""),
        "max_profit": row.get("max_profit", ""),
        "max_loss": row.get("max_loss", ""),
        "rr_actual": row.get("rr_actual", ""),
        "pmp": row.get("pmp", ""),
        "ev": row.get("ev", ""),
        "liquidity_status": row.get("liquidity_status", "UNKNOWN"),
        "paper_approval_status": audited.classification,
        "reject_reason": audited.reject_reason,
        "gamma_ratio_source": row.get("gamma_ratio_source", ""),
        "classification": audited.classification,
        "provenance": PROVENANCE_TAG,
    }
    for col in C2A_EVIDENCE_COLUMNS:
        payload[col] = row.get(col, "")
    return payload


def _audit_replay_candidates(
    candidates_path: Path,
    *,
    run_id: str,
    context_artifact: str | None,
) -> pd.DataFrame:
    df = pd.read_csv(candidates_path)
    context_df = (
        pd.read_csv(context_artifact)
        if context_artifact and Path(context_artifact).is_file()
        else pd.DataFrame()
    )

    rows: list[dict[str, object]] = []
    for _, series in df.iterrows():
        trade_date = str(series.get("trade_date", "")).strip()
        spy_regime = _spy_regime_label(context_df, trade_date)
        audited = _classify_replay_candidate(series, spy_regime_label=spy_regime)
        rows.append(_audit_row_from_series(series, run_id=run_id, audited=audited))
    if not rows:
        return pd.DataFrame(columns=list(_RISK_AUDIT_COLUMNS))
    return pd.DataFrame(rows)


def _audit_spread_candidates(
    candidates_path: Path,
    *,
    run_id: str,
) -> pd.DataFrame:
    spread_rows = load_spread_candidate_rows(candidates_path)
    approvals = build_paper_approval_candidates(spread_rows)
    base = paper_approval_to_dataframe(approvals)
    if base.empty:
        return pd.DataFrame(columns=list(_RISK_AUDIT_COLUMNS))

    rows: list[dict[str, object]] = []
    for _, series in base.iterrows():
        approval_status = str(series.get("approval_status", "")).strip()
        reason = str(series.get("approval_reason", "")).strip()
        failures = str(series.get("failure_reasons", "")).strip()
        if approval_status == "APPROVED_FOR_PAPER_REVIEW":
            classification: GuardClassification = "APPROVED_PAPER"
            reject_reason = ""
        elif approval_status == "INCOMPLETE":
            classification = "REJECTED_MISSING_FIELDS"
            reject_reason = reason or "incomplete_required_fields"
        else:
            classification = _map_approval_failure_to_classification(reason, failures)
            reject_reason = reason or failures

        net = series.get("net_debit_or_credit")
        debit = ""
        credit = ""
        if net is not None and pd.notna(net):
            if float(net) >= 0:
                debit = net
            else:
                credit = abs(float(net))

        rows.append(
            {
                "run_id": run_id,
                "symbol": series.get("symbol", ""),
                "underlying": series.get("symbol", ""),
                "regime_label": "",
                "structure_bias": StructureBias.SKIP.value,
                "playbook": series.get("structure_type", ""),
                "structure": series.get("structure_type", ""),
                "expiration": series.get("expiration", ""),
                "dte": "",
                "long_leg_symbol": series.get("long_leg_symbol", ""),
                "short_leg_symbol": series.get("short_leg_symbol", ""),
                "long_strike": "",
                "short_strike": "",
                "debit": debit,
                "credit": credit,
                "width": series.get("spread_width", ""),
                "max_profit": series.get("max_profit", ""),
                "max_loss": series.get("max_loss", ""),
                "rr_actual": series.get("reward_risk", ""),
                "pmp": series.get("pmp", ""),
                "ev": series.get("expected_value", ""),
                "liquidity_status": series.get("bid_ask_quality", "UNKNOWN"),
                "paper_approval_status": approval_status,
                "reject_reason": reject_reason,
                "classification": classification,
                "provenance": PROVENANCE_TAG,
            }
        )
    return pd.DataFrame(rows)


def _is_spread_candidate_csv(path: Path) -> bool:
    if not path.is_file():
        return False
    df = pd.read_csv(path, nrows=0)
    cols = set(df.columns)
    return "structure_type" in cols and "pmp_for_gate" in cols and "underlying_symbol" in cols


def run_risk_guard(
    base_dir: Path,
    run_id: str,
    candidates_artifact: str,
    paper_only: bool = True,
    *,
    context_artifact: str | None = None,
    staged_files: list[str] | None = None,
    expressions_artifact: str | None = None,
) -> RiskGuardResult:
    if not paper_only:
        raise RuntimeError("PAPER_ONLY_REQUIRED")

    assert_not_halted(base_dir)

    candidates_path = Path(candidates_artifact)
    if not candidates_path.is_file():
        raise FileNotFoundError(f"candidates artifact missing: {candidates_path}")

    risk_path = base_dir / "data/processed/risk" / f"{run_id}_risk_audit.csv"
    risk_path.parent.mkdir(parents=True, exist_ok=True)

    if _is_spread_candidate_csv(candidates_path):
        audit_df = _audit_spread_candidates(candidates_path, run_id=run_id)
    else:
        audit_df = _audit_replay_candidates(
            candidates_path,
            run_id=run_id,
            context_artifact=context_artifact,
        )

    macro_gate = build_macro_paper_gate(
        base_dir,
        run_id=run_id,
        staged_files=staged_files,
    )
    audit_df = apply_am_note_paper_gate_to_audit(audit_df, macro_gate)

    expressions_df = pd.DataFrame()
    expr_path = Path(expressions_artifact or "")
    if expr_path.is_file():
        expressions_df = pd.read_csv(expr_path)
        if run_id and "run_id" in expressions_df.columns:
            expressions_df = expressions_df[
                expressions_df["run_id"].astype(str) == str(run_id)
            ]
    frontier = build_expression_frontier(
        expressions_df,
        base_dir=base_dir,
        run_id=run_id,
    )
    audit_df = apply_frontier_paper_gate_to_audit(audit_df, frontier)

    audit_df.to_csv(risk_path, index=False)
    return RiskGuardResult(risk_audit_artifact=str(risk_path))


def summarize_risk_audit(path: str | Path) -> dict[str, object]:
    p = Path(path)
    if not p.is_file():
        return {"total_candidates": 0}

    df = pd.read_csv(p)
    if df.empty:
        return {"total_candidates": 0}

    col = "classification" if "classification" in df.columns else "approval_status"
    counts = Counter(str(v) for v in df[col].fillna(""))

    approved = counts.get("APPROVED_PAPER", 0) + counts.get("APPROVED_FOR_PAPER_REVIEW", 0)
    paper_gate_withheld = counts.get("PAPER_GATE_WITHHELD", 0)
    frontier_withheld = sum(
        1
        for v in df.get("reject_reason", pd.Series(dtype=str)).fillna("")
        if str(v) == "paper_gate:frontier_review_required"
    )
    parked = (
        counts.get("PARKED_REVIEW", 0)
        + counts.get("PARKED", 0)
        + counts.get(CandidateLoopStatus.PARKED_DATA_GAP.value, 0)
        + counts.get(CandidateLoopStatus.HYDRATION_PENDING.value, 0)
        + counts.get(CandidateLoopStatus.NO_VIABLE_EXPRESSION.value, 0)
        + counts.get(CandidateLoopStatus.PRIMARY_EXPRESSION_SELECTED.value, 0)
        + counts.get(CandidateLoopStatus.WATCH_EXPRESSION_AVAILABLE.value, 0)
        + counts.get(CandidateLoopStatus.ALTERNATES_AVAILABLE.value, 0)
        + counts.get(CandidateLoopStatus.HYDRATED.value, 0)
    )
    rejected_missing = (
        counts.get("REJECTED_MISSING_FIELDS", 0)
        + counts.get(_CONTEXT_GATE_BLOCKED, 0)
        + counts.get(_CONTEXT_GATE_INCOMPLETE, 0)
    )
    rejected_rr = counts.get("REJECTED_RR", 0)
    rejected_pmp = counts.get("REJECTED_PMP", 0)
    rejected_liquidity = counts.get("REJECTED_LIQUIDITY", 0)
    rejected_policy = counts.get("REJECTED_POLICY", 0)
    rejected_legacy = counts.get("REJECTED", 0)
    incomplete = counts.get("INCOMPLETE", 0)

    rejected = (
        rejected_missing
        + rejected_rr
        + rejected_pmp
        + rejected_liquidity
        + rejected_policy
        + rejected_legacy
        + incomplete
    )

    reasons = Counter(
        str(v)
        for v in df.get("reject_reason", df.get("rejection_reason", pd.Series(dtype=str))).fillna("")
        if str(v)
    )
    spread_economics_rejects = sum(
        1
        for v in df.get("reject_reason", pd.Series(dtype=str)).fillna("")
        if str(v).startswith("spread_economics:")
    )
    hydration_pending = counts.get(CandidateLoopStatus.HYDRATION_PENDING.value, 0)
    parked_data_gap = counts.get(CandidateLoopStatus.PARKED_DATA_GAP.value, 0)
    no_viable_expression = counts.get(CandidateLoopStatus.NO_VIABLE_EXPRESSION.value, 0)
    primary_selected = counts.get(CandidateLoopStatus.PRIMARY_EXPRESSION_SELECTED.value, 0)
    watch_expression_available = counts.get(CandidateLoopStatus.WATCH_EXPRESSION_AVAILABLE.value, 0)
    watch_operator_review = counts.get(CandidateLoopStatus.WATCH_OPERATOR_REVIEW.value, 0)
    watch_operator_approved = counts.get(CandidateLoopStatus.WATCH_OPERATOR_APPROVED.value, 0)
    watch_operator_rejected = counts.get(CandidateLoopStatus.WATCH_OPERATOR_REJECTED.value, 0)
    alternates_available = counts.get(CandidateLoopStatus.ALTERNATES_AVAILABLE.value, 0)
    context_gate_rejects = sum(
        1
        for v in df.get("classification", pd.Series(dtype=str)).fillna("")
        if str(v) in {_CONTEXT_GATE_BLOCKED, _CONTEXT_GATE_INCOMPLETE}
    )
    reverse_vrp_symbol_context_rows = 0
    if "source_profile" in df.columns:
        reverse_vrp_symbol_context_rows = int(
            (df["source_profile"].astype(str) == "reverse_vrp").sum()
        )
    spy_backdrop_absent = 0
    if "context_gate_reason" in df.columns:
        spy_backdrop_absent = int(
            (df["context_gate_reason"].astype(str) == "missing_spy_context").sum()
        )
    hydration_expressions_attempted = 0
    if "expression_count" in df.columns:
        hydration_expressions_attempted = int(
            pd.to_numeric(df["expression_count"], errors="coerce").fillna(0).gt(0).sum()
        )
    context_gamma_source_absent = 0
    if "gamma_ratio_source" in df.columns:
        context_gamma_source_absent = int(
            (df["gamma_ratio_source"].astype(str) == "source_absent").sum()
        )

    regime = ""
    if "regime_label" in df.columns:
        non_empty = [str(v) for v in df["regime_label"].dropna() if str(v).strip()]
        regime = non_empty[0] if non_empty else ""

    structure_bias = ""
    if "structure_bias" in df.columns:
        bias_counts = Counter(str(v) for v in df["structure_bias"].fillna("") if str(v))
        structure_bias = bias_counts.most_common(1)[0][0] if bias_counts else ""

    top_reasons = [r for r, _ in reasons.most_common(5) if r]

    return {
        "total_candidates": len(df),
        "approved_paper_only": approved,
        "paper_gate_withheld_am_note": paper_gate_withheld,
        "paper_gate_withheld_frontier": frontier_withheld,
        "parked": parked,
        "rejected": rejected,
        "incomplete": incomplete,
        "rejected_missing_fields": rejected_missing,
        "rejected_rr": rejected_rr,
        "rejected_pmp": rejected_pmp,
        "rejected_liquidity": rejected_liquidity,
        "rejected_policy": rejected_policy,
        "rejected_spread_economics": spread_economics_rejects,
        "hydration_pending": hydration_pending,
        "parked_data_gap": parked_data_gap,
        "no_viable_expression": no_viable_expression,
        "primary_expression_selected": primary_selected,
        "watch_expression_available": watch_expression_available,
        "watch_operator_review": watch_operator_review,
        "watch_operator_approved": watch_operator_approved,
        "watch_operator_rejected": watch_operator_rejected,
        "alternates_available": alternates_available,
        "context_gate_rejects": context_gate_rejects,
        "reverse_vrp_symbol_context_rows": reverse_vrp_symbol_context_rows,
        "spy_backdrop_absent": spy_backdrop_absent,
        "hydration_expressions_attempted": hydration_expressions_attempted,
        "context_gamma_source_absent": context_gamma_source_absent,
        "top_rejection_reasons": top_reasons,
        "regime_label": regime,
        "structure_bias": structure_bias,
    }
