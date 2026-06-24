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
)
from qops.advisory.dealer_structure import DealerStructureAssessment, assess_dealer_structure
from qops.advisory.expression_frontier import (
    ExpressionFrontierResult,
    build_expression_frontier,
    format_expression_frontier_section,
)
from qops.advisory.spread_skeptic import SpreadSkepticNote, build_spread_skeptic_notes
from qops.runtime.orb_manifest import OrbRunManifest


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
    if gate.am_note_status != "PARSED":
        return "context incomplete; paper approval withheld"
    return gate.paper_gate_macro_status


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
        expressions_df = pd.read_csv(expressions_path)
        if manifest.run_id and "run_id" in expressions_df.columns:
            expressions_df = expressions_df[
                expressions_df["run_id"].astype(str) == str(manifest.run_id)
            ]

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

    advisory_dir = base_dir / "data/advisory"
    advisory_dir.mkdir(parents=True, exist_ok=True)
    frontier_csv = advisory_dir / f"{manifest.run_id}_expression_frontier.csv"
    if frontier.expression_rows:
        pd.DataFrame(frontier.expression_rows).to_csv(frontier_csv, index=False)
    else:
        frontier_csv = None

    payload: dict[str, object] = {
        "run_id": manifest.run_id,
        "am_note_status": gate.am_note_status,
        "macro_context_state": gate.macro_context_state,
        "paper_gate_macro_status": gate.paper_gate_macro_status,
        "macro_context_summary": gate.macro_context_summary,
        "dealer_positioning_summary": gate.dealer_positioning_summary
        or dealer.structure_summary,
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
        "frontier_review_required_before_paper": frontier.frontier_review_required_before_paper,
        "expression_frontier_summaries": [asdict(s) for s in frontier.symbol_summaries],
        "expression_frontier_rows": frontier.expression_rows,
        "expression_frontier_artifact": str(frontier_csv) if frontier_csv else "",
    }
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
