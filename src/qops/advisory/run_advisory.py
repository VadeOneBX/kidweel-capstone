"""Assemble run-level advisory artifacts (AM note gate, dealer structure, spread skeptic)."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, Field

from qops.advisory.am_note_gate import (
    MacroPaperGate,
    PreAmStructureFields,
    build_macro_paper_gate,
    build_pre_am_structure_fields,
    run_date_from_run_id,
)
from qops.advisory.private_context_builder import load_sanitized_private_context
from qops.ingest.morning_regime_upgrade import (
    discover_upgraded_morning_regime_workbooks,
    fast_advisory_candidate_to_dict,
    run_morning_regime_intake,
)
from qops.advisory.dealer_structure import DealerStructureAssessment, assess_dealer_structure
from qops.advisory.expression_frontier import (
    ExpressionFrontierResult,
    build_expression_frontier,
    format_expression_frontier_section,
)
from qops.advisory.run_readiness import build_operator_next_actions
from qops.advisory.spread_skeptic import SpreadSkepticNote, build_spread_skeptic_notes
from qops.runtime.orb_manifest import OrbRunManifest
from qops.risk.guard_runner import summarize_risk_audit
from qops.schemas.candidate_loop import CandidateLoopStatus, SpreadExpressionStatus


def _json_default(value: object) -> object:
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(value, float) and (value != value):
        return None
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


class RunAdvisoryResult(BaseModel):
    advisory_json_artifact: str
    run_advisory: dict[str, object] = Field(default_factory=dict)


def _macro_posture_label(gate: MacroPaperGate) -> str:
    if gate.parsed_note and gate.parsed_note.advisory_bias:
        return gate.parsed_note.advisory_bias
    audit = getattr(gate, "macro_context", None)
    if audit is not None and getattr(audit, "status", "") in {
        "MACRO_CONTEXT_UNPARSED_NON_BLOCKING",
        "MACRO_CONTEXT_MISSING_NON_BLOCKING",
    }:
        return "macro context degraded; non-blocking"
    if gate.am_note_status != "PARSED" and gate.macro_context_state != "MANUAL_CONTEXT_OVERRIDE":
        return "macro context degraded; non-blocking"
    return gate.paper_gate_macro_status


_AUDIT_TO_MORNING_MACRO = {
    "MACRO_CONTEXT_READY": "READY",
    "MACRO_CONTEXT_READY_LOW_CONFIDENCE": "READY_LOW_CONFIDENCE",
    "MACRO_CONTEXT_UNPARSED_NON_BLOCKING": "UNPARSED_NON_BLOCKING",
    "MACRO_CONTEXT_MISSING_NON_BLOCKING": "MISSING_NON_BLOCKING",
    "MANUAL_CONTEXT_OVERRIDE": "READY_LOW_CONFIDENCE",
}


def _morning_macro_context(gate: MacroPaperGate, private_lanes: dict[str, object] | None = None) -> str:
    # Private vendor macro is authoritative when the artifact exists.
    # PARSE_FAILED/PARTIAL/READY must not collapse to MISSING when a file was found.
    # Only MISSING_NON_BLOCKING falls through to AM-note / workbook prose degrade path.
    if private_lanes:
        lane = str(private_lanes.get("macro_context", "") or "")
        if lane in {
            "READY",
            "READY_LOW_CONFIDENCE",
            "PARTIAL",
            "PARSE_FAILED_NON_BLOCKING",
        }:
            return lane
    audit = getattr(gate, "macro_context", None)
    if audit is not None:
        mapped = _AUDIT_TO_MORNING_MACRO.get(str(getattr(audit, "status", "") or ""))
        if mapped:
            return mapped
    if gate.macro_context_state == "AM_NOTE_CONTEXT_READY":
        return "READY"
    if gate.macro_context_state == "MANUAL_CONTEXT_OVERRIDE":
        return "READY_LOW_CONFIDENCE"
    if gate.am_note_status == "AVAILABLE_NOT_PARSED":
        return "UNPARSED_NON_BLOCKING"
    if gate.am_note_status == "NOT_AVAILABLE":
        return "MISSING_NON_BLOCKING"
    return "READY_LOW_CONFIDENCE"


def _has_reason_token(risk_df: pd.DataFrame, tokens: tuple[str, ...]) -> bool:
    if risk_df.empty or "reject_reason" not in risk_df.columns:
        return False
    values = risk_df["reject_reason"].fillna("").astype(str).str.lower()
    return any(values.str.contains(token, regex=False).any() for token in tokens)


def _build_morning_regime_status(
    manifest: OrbRunManifest,
    gate: MacroPaperGate,
    risk_df: pd.DataFrame,
    expressions_df: pd.DataFrame,
    private_context: dict[str, object] | None = None,
) -> dict[str, object]:
    summary = summarize_risk_audit(manifest.risk_audit_artifact or "")
    candidate_count = int(summary.get("total_candidates", 0) or 0)
    no_viable = int(summary.get("no_viable_expression", 0) or 0)
    watch_count = int(summary.get("watch_expression_available", 0) or 0)
    primary_count = int(summary.get("primary_expression_selected", 0) or 0)
    approved_count = int(summary.get("approved_paper_only", 0) or 0)
    parked_count = int(summary.get("parked", 0) or 0)
    rejected_count = int(summary.get("rejected", 0) or 0)
    data_gap_count = int(summary.get("parked_data_gap", 0) or 0)
    hydration_pending = int(summary.get("hydration_pending", 0) or 0)
    hydrated_attempts = int(summary.get("hydration_expressions_attempted", 0) or 0)

    credential_parked = _has_reason_token(
        risk_df,
        ("credential", "auth", "alpaca_missing", "missing_key_secret"),
    )
    geometry_rejects = _has_reason_token(
        risk_df,
        ("spread_economics", "reward_risk", "no_viable_expression", "expression_search_exhausted"),
    )

    if credential_parked:
        hydration = "PARKED_CREDENTIAL_ERROR"
    elif data_gap_count > 0 and hydrated_attempts == 0:
        hydration = "PARKED_DATA_GAP"
    elif (data_gap_count > 0 or hydration_pending > 0) and hydrated_attempts > 0:
        hydration = "PARTIAL"
    else:
        hydration = "READY"

    if candidate_count == 0:
        options_discovery = "NO_CANDIDATES"
    elif hydration in {"PARKED_CREDENTIAL_ERROR", "PARKED_DATA_GAP"} and hydrated_attempts == 0:
        options_discovery = "PARKED_DATA_GAP"
    elif hydration == "PARTIAL":
        options_discovery = "PARTIAL"
    else:
        options_discovery = "READY"

    if hydration in {"PARKED_CREDENTIAL_ERROR", "PARKED_DATA_GAP"} and hydrated_attempts == 0:
        structure_build = "PARKED_HYDRATION_REQUIRED"
    elif no_viable > 0 and (primary_count + watch_count + approved_count) == 0:
        structure_build = "NO_VIABLE_STRUCTURE"
    elif no_viable > 0:
        structure_build = "PARTIAL"
    else:
        structure_build = "READY"

    selected_expression: str | None = None
    if not expressions_df.empty:
        prim = expressions_df[
            expressions_df.get("expression_status", pd.Series(dtype=str)).astype(str)
            == SpreadExpressionStatus.PRIMARY.value
        ]
        if not prim.empty:
            selected_expression = str(prim.iloc[0].get("expression_id", "") or "").strip() or None
    primary_evidence = primary_count > 0 or selected_expression is not None

    if approved_count > 0 and primary_evidence:
        quality_gate = "PASS"
    elif watch_count > 0 and approved_count == 0:
        quality_gate = "WATCH"
    elif candidate_count == 0:
        quality_gate = "NO_ACTION_QUALITY"
    elif structure_build == "NO_VIABLE_STRUCTURE" or geometry_rejects:
        quality_gate = "NO_ACTION_QUALITY"
    else:
        quality_gate = "FAIL"

    if quality_gate != "PASS":
        selected_expression = None

    if not gate.paper_approval_allowed:
        paper_action = "FORBIDDEN_SAFETY"
    elif credential_parked:
        paper_action = "WITHHELD_CREDENTIALS"
    elif hydration in {"PARKED_DATA_GAP"} or options_discovery == "PARKED_DATA_GAP":
        paper_action = "WITHHELD_DATA_GAP"
    elif quality_gate == "PASS":
        paper_action = "ALLOWED"
    else:
        paper_action = "WITHHELD_QUALITY"

    reasons = list(summary.get("top_rejection_reasons", []))
    if watch_count > 0 and "operator_watch_review_required" not in reasons:
        reasons = ["operator_watch_review_required", *reasons]
    top_reasons = reasons[:5]

    private_lanes = {}
    if private_context and isinstance(private_context.get("lanes"), dict):
        private_lanes = private_context["lanes"]

    morning_core = {
        "run_status": manifest.status,
        "woke": True,
        "macro_context": _morning_macro_context(gate, private_lanes),
        "flow_context": private_lanes.get("flow_context", "MISSING_NON_BLOCKING"),
        "skew_context": private_lanes.get("skew_context", "MISSING_NON_BLOCKING"),
        "vol_context": private_lanes.get("vol_context", "MISSING_NON_BLOCKING"),
        "index_levels_context": private_lanes.get("index_levels_context", "MISSING_NON_BLOCKING"),
        "hydration": hydration,
        "options_discovery": options_discovery,
        "structure_build": structure_build,
        "quality_gate": quality_gate,
        "paper_action": paper_action,
        "selected_expression": selected_expression,
        "candidate_count": candidate_count,
        "parked_count": parked_count,
        "rejected_count": rejected_count,
        "top_reasons": top_reasons,
    }
    actions = build_operator_next_actions(
        morning=morning_core,
        private_vendor_context=private_context if isinstance(private_context, dict) else None,
        stored_morning=morning_core,
    )
    next_action = "; ".join(
        f"{a['id']}: {a['command']}" for a in actions if a.get("command")
    )
    if quality_gate == "WATCH" and selected_expression is None and not next_action:
        next_action = "Explicit operator WATCH review/promotion required; no auto-promotion."
    elif paper_action == "WITHHELD_QUALITY" and not any(
        a.get("id") == "diagnose_quote_hydration" for a in actions
    ):
        # Keep quality prose when hydration is not the parked reason.
        if not next_action or next_action.startswith("view_readiness:"):
            next_action = "No paper action. Quality gate withheld selection."

    return {
        **morning_core,
        "operator_next_action": next_action,
        "operator_next_actions": actions,
    }


def build_run_advisory(
    base_dir: Path,
    manifest: OrbRunManifest,
    *,
    staged_files: list[str] | None = None,
) -> RunAdvisoryResult:
    gate = build_macro_paper_gate(
        base_dir,
        run_id=manifest.run_id,
        staged_files=staged_files or manifest.staged_files,
    )
    context_path = Path(manifest.context_artifact or "")
    context_df = (
        pd.read_csv(context_path)
        if context_path.is_file()
        else pd.DataFrame()
    )
    pre_am = build_pre_am_structure_fields(context_df)
    dealer = assess_dealer_structure(context_df)

    expressions_df = pd.DataFrame()
    expressions_path = Path(manifest.expressions_artifact or "")
    if expressions_path.is_file():
        try:
            expressions_df = pd.read_csv(expressions_path)
        except pd.errors.EmptyDataError:
            expressions_df = pd.DataFrame()
        if manifest.run_id and "run_id" in expressions_df.columns:
            expressions_df = expressions_df[
                expressions_df["run_id"].astype(str) == str(manifest.run_id)
            ]
    risk_df = pd.DataFrame()
    risk_path = Path(manifest.risk_audit_artifact or "")
    if risk_path.is_file():
        risk_df = pd.read_csv(risk_path)

    spot_by_symbol: dict[str, float] = {}
    if not context_df.empty and "symbol" in context_df.columns:
        for _, row in context_df.iterrows():
            sym = str(row.get("symbol", "")).strip().upper()
            if sym and sym not in spot_by_symbol:
                from qops.backtest.spotgamma_replay_builder import parse_notes_kv
                from qops.ingest.spotgamma_loader import parse_numeric

                notes = parse_notes_kv(str(row.get("notes", "") or ""))
                px = parse_numeric(notes.get("current_price"))
                if px is not None:
                    spot_by_symbol[sym] = float(px)

    skeptic_notes = build_spread_skeptic_notes(
        expressions_df,
        macro_posture=_macro_posture_label(gate),
        spot_by_symbol=spot_by_symbol,
    )

    frontier = build_expression_frontier(
        expressions_df,
        base_dir=base_dir,
        run_id=manifest.run_id,
    )

    session_date = run_date_from_run_id(manifest.run_id)
    private_context = load_sanitized_private_context(base_dir, run_date=session_date)

    macro_context_summary = gate.macro_context_summary
    private_lanes = (
        private_context.get("lanes") if isinstance(private_context.get("lanes"), dict) else {}
    )
    if str(private_lanes.get("macro_context", "") or "") == "PARTIAL" and (
        gate.macro_context.status == "MACRO_CONTEXT_MISSING_NON_BLOCKING"
        or gate.macro_context.parse_status == "MISSING_OPTIONAL_CONTEXT"
    ):
        macro_context_summary = (
            "Private macro context is PARTIAL. "
            "AM-note / Founder's Note prose remains missing or incomplete. "
            "Morning loop continues with degraded macro confidence."
        )

    dealer_positioning_summary = gate.dealer_positioning_summary or dealer.structure_summary
    if not gate.am_note_required_before_paper:
        lowered = dealer_positioning_summary.lower()
        if "required before paper" in lowered or "still required" in lowered:
            dealer_positioning_summary = dealer.structure_summary

    staged = staged_files or manifest.staged_files
    flow_intake_payload: dict[str, object] | None = None
    morning_regime_audit_artifact = ""
    morning_regime_workbooks = discover_upgraded_morning_regime_workbooks(
        base_dir,
        run_date=session_date,
        staged_files=staged,
    )
    if morning_regime_workbooks:
        intake, audit_path = run_morning_regime_intake(
            base_dir,
            morning_regime_workbooks[0],
        )
        morning_regime_audit_artifact = str(audit_path)
        flow_intake_payload = {
            "workbook": intake.workbook,
            "workbook_format": "upgraded",
            "sheets_found": intake.sheets_found,
            "fast_advisory_candidates": [
                fast_advisory_candidate_to_dict(c) for c in intake.fast_advisory_candidates
            ],
            "image_ocr_used": intake.image_ocr_used,
            "paper_submission_status": "gated_not_submitted",
        }

    advisory_dir = base_dir / "data/advisory"
    advisory_dir.mkdir(parents=True, exist_ok=True)
    frontier_csv = advisory_dir / f"{manifest.run_id}_expression_frontier.csv"
    if frontier.expression_rows:
        pd.DataFrame(frontier.expression_rows).to_csv(frontier_csv, index=False)
    else:
        frontier_csv = None

    morning_status = _build_morning_regime_status(
        manifest,
        gate,
        risk_df,
        expressions_df,
        private_context,
    )

    payload: dict[str, object] = {
        "run_id": manifest.run_id,
        "am_note_status": gate.am_note_status,
        "macro_context_state": gate.macro_context_state,
        "paper_gate_macro_status": gate.paper_gate_macro_status,
        "macro_context_summary": macro_context_summary,
        "dealer_positioning_summary": dealer_positioning_summary,
        "macro_catalyst_summary": gate.macro_catalyst_summary,
        "spread_posture": gate.spread_posture,
        "am_note_required_before_paper": gate.am_note_required_before_paper,
        "paper_approval_allowed": gate.paper_approval_allowed,
        "pre_am_structure": asdict(pre_am),
        "dealer_structure": {
            "gamma_regime": dealer.gamma_regime,
            "put_wall_movement": dealer.put_wall_movement,
            "call_wall_movement": dealer.call_wall_movement,
            "advisory_bias": dealer.advisory_bias,
            "structure_summary": dealer.structure_summary,
        },
        "spread_skeptic_notes": [asdict(n) for n in skeptic_notes],
        "morning_regime_status": morning_status,
        "operator_next_actions": morning_status.get("operator_next_actions", []),
        "operator_next_action": morning_status.get("operator_next_action", ""),
        "macro_context_audit": {
            "status": gate.macro_context.status,
            "source_type": gate.macro_context.source_type,
            "parse_status": gate.macro_context.parse_status,
            "source_file": gate.macro_context.source_file,
            "warnings": list(gate.macro_context.warnings),
            "confidence": gate.macro_context.confidence,
        },
        "private_vendor_context": private_context,
        "frontier_review_required_before_paper": frontier.frontier_review_required_before_paper,
        "expression_frontier_summaries": [asdict(s) for s in frontier.symbol_summaries],
        "expression_frontier_rows": frontier.expression_rows,
        "expression_frontier_artifact": str(frontier_csv) if frontier_csv else "",
    }
    if flow_intake_payload is not None:
        payload["morning_regime_flow"] = flow_intake_payload
        payload["morning_regime_audit_artifact"] = morning_regime_audit_artifact
        payload["morning_regime_upgrade"] = flow_intake_payload
        payload["morning_regime_upgrade_audit_artifact"] = morning_regime_audit_artifact
    if gate.parsed_note is not None:
        payload["am_note_parsed"] = asdict(gate.parsed_note)

    json_path = advisory_dir / f"{manifest.run_id}_run_advisory.json"
    json_path.write_text(
        json.dumps(payload, indent=2, default=_json_default),
        encoding="utf-8",
    )
    return RunAdvisoryResult(advisory_json_artifact=str(json_path), run_advisory=payload)


def format_spread_skeptic_section(notes: list[SpreadSkepticNote], limit: int = 8) -> str:
    if not notes:
        return "- (no hydrated expressions for skeptic review)"
    lines: list[str] = []
    for note in notes[:limit]:
        lines.append(
            f"### {note.symbol} ({note.expression_status})\n\n"
            f"{note.interesting_because}\n\n"
            f"{note.but_challenge}\n\n"
            f"{note.operator_check}\n\n"
            f"{note.promotion_condition}\n\n"
            f"Macro overlay: {note.macro_overlay}\n"
        )
    if len(notes) > limit:
        lines.append(f"\n_(+{len(notes) - limit} more in run_advisory JSON)_\n")
    return "\n".join(lines)
