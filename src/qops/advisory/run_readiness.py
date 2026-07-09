"""Morning run readiness lanes (macro / hydration / selection) — degrade-not-block."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from qops.advisory.am_note_gate import MacroPaperGate
from qops.backtest.alpaca_greeks_layer import check_alpaca_market_data_credentials
from qops.risk.guard_runner import summarize_risk_audit
from qops.schemas.candidate_loop import CandidateLoopStatus


@dataclass(frozen=True, slots=True)
class MacroReadinessLane:
    status: str
    source: str
    summary: str
    blocks_run: bool = False


@dataclass(frozen=True, slots=True)
class HydrationReadinessLane:
    status: str
    reason: str
    parked_count: int = 0


@dataclass(frozen=True, slots=True)
class SelectionReadinessLane:
    status: str
    reason: str
    parked_count: int = 0


@dataclass(frozen=True, slots=True)
class RunReadiness:
    woke: bool
    macro: MacroReadinessLane
    hydration: HydrationReadinessLane
    selection: SelectionReadinessLane

    def to_dict(self) -> dict[str, object]:
        return {
            "woke": self.woke,
            "macro": asdict(self.macro),
            "hydration": asdict(self.hydration),
            "selection": asdict(self.selection),
        }


def _reason_token(risk_df: pd.DataFrame, tokens: tuple[str, ...]) -> str:
    if risk_df.empty or "reject_reason" not in risk_df.columns:
        return ""
    for raw in risk_df["reject_reason"].fillna("").astype(str):
        lower = raw.lower()
        if any(token in lower for token in tokens):
            return raw
    if "data_gap_reason" in risk_df.columns:
        for raw in risk_df["data_gap_reason"].fillna("").astype(str):
            lower = raw.lower()
            if any(token in lower for token in tokens):
                return raw
    return ""


def _hydration_lane_from_artifacts(
    risk_df: pd.DataFrame,
    *,
    risk_audit_artifact: str | None,
    hydration_skip_reason: str | None,
) -> HydrationReadinessLane:
    summary = summarize_risk_audit(risk_audit_artifact or "")
    parked_data_gap = int(summary.get("parked_data_gap", 0) or 0)
    candidate_count = int(summary.get("total_candidates", 0) or 0)

    credential_reason = (
        hydration_skip_reason
        or _reason_token(
            risk_df,
            ("credential_error", "no_credential_pair", "missing_credentials", "alpaca_missing"),
        )
    )
    cred = check_alpaca_market_data_credentials()
    if credential_reason or cred.credential_status != "READY":
        detail = cred.detail or "no_credential_pair"
        if credential_reason and credential_reason.startswith("credential_error:"):
            reason = credential_reason
        elif credential_reason:
            reason = f"credential_error:{credential_reason}"
        else:
            reason = f"credential_error:{detail}"
        return HydrationReadinessLane(
            status="PARKED_CREDENTIAL_ERROR",
            reason=reason,
            parked_count=candidate_count or parked_data_gap or len(risk_df),
        )

    if parked_data_gap > 0:
        reason = _reason_token(risk_df, ("data_gap", "no_chain", "hydration")) or "parked_data_gap"
        return HydrationReadinessLane(
            status="PARKED_DATA_GAP",
            reason=reason,
            parked_count=parked_data_gap,
        )

    hydration_pending = int(summary.get("hydration_pending", 0) or 0)
    if hydration_pending > 0:
        return HydrationReadinessLane(
            status="PARTIAL",
            reason="expression_hydration_pending",
            parked_count=hydration_pending,
        )

    return HydrationReadinessLane(status="READY", reason="", parked_count=0)


def _selection_lane(
    risk_df: pd.DataFrame,
    hydration: HydrationReadinessLane,
) -> SelectionReadinessLane:
    if hydration.status in {"PARKED_CREDENTIAL_ERROR", "PARKED_DATA_GAP"}:
        return SelectionReadinessLane(
            status="PARKED",
            reason=hydration.reason,
            parked_count=hydration.parked_count,
        )

    if risk_df.empty:
        return SelectionReadinessLane(status="READY", reason="", parked_count=0)

    col = "classification" if "classification" in risk_df.columns else ""
    if not col:
        return SelectionReadinessLane(status="READY", reason="", parked_count=0)

    parked_statuses = {
        CandidateLoopStatus.PARKED_DATA_GAP.value,
        CandidateLoopStatus.HYDRATION_PENDING.value,
        CandidateLoopStatus.PARKED_REVIEW.value,
    }
    parked_mask = risk_df[col].astype(str).isin(parked_statuses)
    parked_count = int(parked_mask.sum())
    if parked_count == len(risk_df) and parked_count > 0:
        reason = _reason_token(risk_df, ("no_viable", "watch", "quality", "spread_economics"))
        return SelectionReadinessLane(
            status="PARKED",
            reason=reason or "selection_parked_pending_hydration_or_review",
            parked_count=parked_count,
        )

    watch_count = int(
        (risk_df[col].astype(str) == CandidateLoopStatus.WATCH_EXPRESSION_AVAILABLE.value).sum()
    )
    if watch_count > 0:
        return SelectionReadinessLane(
            status="WATCH",
            reason="operator_watch_review_required",
            parked_count=watch_count,
        )

    approved = int(
        risk_df[col].astype(str).isin({"APPROVED_PAPER", "APPROVED_FOR_PAPER_REVIEW"}).sum()
    )
    if approved > 0:
        return SelectionReadinessLane(status="READY", reason="primary_expression_available", parked_count=0)

    return SelectionReadinessLane(status="READY", reason="", parked_count=0)


def build_run_readiness(
    gate: MacroPaperGate,
    risk_df: pd.DataFrame,
    *,
    risk_audit_artifact: str | None = None,
    hydration_skip_reason: str | None = None,
) -> RunReadiness:
    macro = MacroReadinessLane(
        status=gate.macro_readiness_status,
        source=gate.macro_context_source,
        summary=gate.macro_context_summary,
        blocks_run=False,
    )
    hydration = _hydration_lane_from_artifacts(
        risk_df,
        risk_audit_artifact=risk_audit_artifact,
        hydration_skip_reason=hydration_skip_reason,
    )
    selection = _selection_lane(risk_df, hydration)
    return RunReadiness(woke=True, macro=macro, hydration=hydration, selection=selection)


def run_advisory_json_path(base_dir: Path, run_id: str) -> Path:
    return base_dir / "data" / "advisory" / f"{run_id}_run_advisory.json"


def format_readiness_report(readiness: dict[str, object]) -> str:
    macro = readiness.get("macro", {})
    hydration = readiness.get("hydration", {})
    selection = readiness.get("selection", {})
    if not isinstance(macro, dict):
        macro = {}
    if not isinstance(hydration, dict):
        hydration = {}
    if not isinstance(selection, dict):
        selection = {}

    lines = [
        "Morning Regime readiness:",
        f"- woke: {readiness.get('woke', False)}",
        f"- macro: {macro.get('status', '')} / {macro.get('source', '')}",
        f"- hydration: {hydration.get('status', '')} / {hydration.get('reason', '')}",
        f"- selection: {selection.get('status', '')} / {selection.get('reason', '')}",
        f"- hydration_parked_count: {hydration.get('parked_count', 0)}",
        f"- selection_parked_count: {selection.get('parked_count', 0)}",
    ]
    morning = readiness.get("morning_regime_status")
    if isinstance(morning, dict):
        lines.extend(
            [
                "",
                "Morning Regime lanes (quality taxonomy):",
                f"- macro_context: {morning.get('macro_context', '')}",
                f"- hydration: {morning.get('hydration', '')}",
                f"- options_discovery: {morning.get('options_discovery', '')}",
                f"- structure_build: {morning.get('structure_build', '')}",
                f"- quality_gate: {morning.get('quality_gate', '')}",
                f"- paper_action: {morning.get('paper_action', '')}",
                f"- selected_expression: {morning.get('selected_expression')}",
            ]
        )
    return "\n".join(lines)
