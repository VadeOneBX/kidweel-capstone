from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from pydantic import BaseModel

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
from qops.schemas.playbook import AllowedPlaybook, StructureBias

PROVENANCE_TAG = "guard_c1e_morning_risk_audit"

GuardClassification = str

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
    "classification",
    "provenance",
)


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
    spread_gaps = spread_contract_gaps(row)
    has_spy = bool(row.get("has_spy_context"))

    playbook_decision = _playbook_decision_for_row(row)
    allowed = playbook_decision.allowed_playbook
    structure_bias = StructureBias.SKIP.value
    regime = spy_regime_label or ""

    if not symbol:
        return _ReplayAudit(
            "REJECTED_MISSING_FIELDS",
            "context_gate:missing_symbol",
            structure_bias,
            allowed.value,
            regime,
            spread_gaps,
            ["missing_symbol"],
        )
    if not trade_date:
        return _ReplayAudit(
            "REJECTED_MISSING_FIELDS",
            "context_gate:missing_trade_date",
            structure_bias,
            allowed.value,
            regime,
            spread_gaps,
            ["missing_trade_date"],
        )
    if context_gaps:
        return _ReplayAudit(
            "REJECTED_MISSING_FIELDS",
            "context_gate:" + ",".join(context_gaps),
            structure_bias,
            allowed.value,
            regime,
            spread_gaps,
            context_gaps,
        )
    if spread_gaps:
        return _ReplayAudit(
            "REJECTED_MISSING_FIELDS",
            "spread_economics:" + ",".join(spread_gaps),
            structure_bias,
            allowed.value,
            regime,
            spread_gaps,
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
    if not has_spy:
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
    return {
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
        "classification": audited.classification,
        "provenance": PROVENANCE_TAG,
    }


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
    parked = counts.get("PARKED_REVIEW", 0) + counts.get("PARKED", 0)
    rejected_missing = counts.get("REJECTED_MISSING_FIELDS", 0)
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
        "parked": parked,
        "rejected": rejected,
        "incomplete": incomplete,
        "rejected_missing_fields": rejected_missing,
        "rejected_rr": rejected_rr,
        "rejected_pmp": rejected_pmp,
        "rejected_liquidity": rejected_liquidity,
        "rejected_policy": rejected_policy,
        "rejected_spread_economics": spread_economics_rejects,
        "top_rejection_reasons": top_reasons,
        "regime_label": regime,
        "structure_bias": structure_bias,
    }
