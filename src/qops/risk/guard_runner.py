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

PROVENANCE_TAG = "guard_c1d_morning_risk_audit"

RiskClassification = str  # APPROVED_FOR_PAPER_REVIEW | PARKED | REJECTED | INCOMPLETE


class RiskGuardResult(BaseModel):
    risk_audit_artifact: str


@dataclass(frozen=True, slots=True)
class _ReplayRiskRow:
    symbol: str
    trade_date: str
    source_profile: str
    structure_bias: str
    allowed_playbook: str
    classification: RiskClassification
    rejection_reason: str
    has_spy_context: bool
    missing_fields: str


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


def _classify_replay_candidate(
    row: pd.Series,
    *,
    spy_regime_label: str | None,
) -> _ReplayRiskRow:
    symbol = str(row.get("symbol", "")).strip().upper()
    trade_date = str(row.get("trade_date", "")).strip()
    source_profile = str(row.get("source_profile", "")).strip()
    missing_fields = str(row.get("missing_fields", "") or "").strip()
    has_spy = bool(row.get("has_spy_context"))

    structure_bias = StructureBias.SKIP
    gamma = row.get("gamma_ratio")
    gamma_ratio = float(gamma) if gamma is not None and pd.notna(gamma) else None

    env = EnvironmentSnapshot(
        symbol=symbol or "UNKNOWN",
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
    playbook_decision = select_allowed_playbook(symbol or "UNKNOWN", structure_bias, env)
    allowed = playbook_decision.allowed_playbook

    failures: list[str] = []
    if not symbol:
        failures.append("missing_symbol")
    if not trade_date:
        failures.append("missing_trade_date")
    if missing_fields:
        failures.append("missing_required_fields")

    if failures:
        classification: RiskClassification = "REJECTED"
        reason = failures[0]
    elif allowed == AllowedPlaybook.SKIP:
        classification = "PARKED"
        reason = playbook_decision.decision_reason or "structure_resolves_to_skip"
    elif not has_spy:
        classification = "PARKED"
        reason = "missing_spy_context"
    else:
        classification = "PARKED"
        reason = "replay_staging_awaiting_spread_math"

    return _ReplayRiskRow(
        symbol=symbol,
        trade_date=trade_date,
        source_profile=source_profile,
        structure_bias=structure_bias.value,
        allowed_playbook=allowed.value,
        classification=classification,
        rejection_reason=reason,
        has_spy_context=has_spy,
        missing_fields=missing_fields,
    )


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
        rows.append(
            {
                "run_id": run_id,
                "symbol": audited.symbol,
                "trade_date": audited.trade_date,
                "source_profile": audited.source_profile,
                "structure_bias": audited.structure_bias,
                "allowed_playbook": audited.allowed_playbook,
                "classification": audited.classification,
                "rejection_reason": audited.rejection_reason,
                "has_spy_context": audited.has_spy_context,
                "missing_fields": audited.missing_fields,
                "regime_label": spy_regime or "",
                "provenance": PROVENANCE_TAG,
            }
        )
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
        return base.assign(run_id=run_id, classification="", provenance=PROVENANCE_TAG)

    base = base.rename(columns={"approval_status": "classification", "approval_reason": "rejection_reason"})
    base.insert(0, "run_id", run_id)
    base["provenance"] = PROVENANCE_TAG
    return base


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
    reasons = Counter(str(v) for v in df.get("rejection_reason", pd.Series(dtype=str)).fillna("") if str(v))

    parked = counts.get("PARKED", 0)
    approved = counts.get("APPROVED_FOR_PAPER_REVIEW", 0)
    rejected = counts.get("REJECTED", 0)
    incomplete = counts.get("INCOMPLETE", 0)

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
        "top_rejection_reasons": top_reasons,
        "regime_label": regime,
        "structure_bias": structure_bias,
    }
