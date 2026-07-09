from __future__ import annotations

from pathlib import Path

import pandas as pd
from pydantic import BaseModel

from qops.advisory.expression_frontier import (
    SymbolFrontierSummary,
    format_expression_frontier_section,
)
from qops.advisory.idea_distillation import (
    distill_subagent_ideas,
    format_policy_votes_section,
)
from qops.advisory.run_advisory import build_run_advisory, format_spread_skeptic_section
from qops.advisory.spread_skeptic import SpreadSkepticNote
from qops.advisory.subagent_ideas import load_tier3_ideas
from qops.pipeline.alpaca_hydration_loop import summarize_expression_artifact
from qops.risk.guard_runner import summarize_risk_audit
from qops.runtime.orb_manifest import OrbRunManifest


class ClaudeBriefResult(BaseModel):
    advisory_artifact: str


def _format_reasons(reasons: list[str]) -> str:
    if not reasons:
        return "- (none recorded)"
    return "\n".join(f"- `{reason}`" for reason in reasons)


def generate_claude_brief(
    base_dir: Path,
    manifest: OrbRunManifest,
) -> ClaudeBriefResult:
    required = [
        manifest.context_artifact,
        manifest.candidates_artifact,
        manifest.risk_audit_artifact,
    ]

    missing = [p for p in required if not p or not Path(p).exists()]
    if missing:
        raise RuntimeError(f"ADVISORY_BLOCKED_MISSING_ARTIFACTS:{missing}")

    summary = summarize_risk_audit(manifest.risk_audit_artifact or "")
    run_advisory_result = build_run_advisory(base_dir, manifest)
    advisory_payload = run_advisory_result.run_advisory

    expressions_path = Path(manifest.expressions_artifact or "")
    if not expressions_path.is_file() and manifest.run_id:
        from qops.pipeline.alpaca_hydration_loop import expressions_artifact_path

        expressions_path = expressions_artifact_path(base_dir, manifest.run_id)
    expr_summary: dict[str, int] = {}
    expr_df = pd.DataFrame()
    if expressions_path.is_file():
        expr_df = pd.read_csv(expressions_path)
        if manifest.run_id and "run_id" in expr_df.columns:
            expr_df = expr_df[expr_df["run_id"].astype(str) == str(manifest.run_id)]
        expr_summary = summarize_expression_artifact(expr_df)

    skeptic_raw = advisory_payload.get("spread_skeptic_notes", [])
    skeptic_notes = [
        SpreadSkepticNote(**item) for item in skeptic_raw if isinstance(item, dict)
    ]
    frontier_raw = advisory_payload.get("expression_frontier_summaries", [])
    frontier_summaries = [
        SymbolFrontierSummary(**item) for item in frontier_raw if isinstance(item, dict)
    ]

    context_df = pd.read_csv(manifest.context_artifact or "")
    tier3_artifacts = load_tier3_ideas(base_dir, manifest.run_date, manifest.run_id)
    distillation = distill_subagent_ideas(
        tier3_artifacts,
        regime_label=str(summary.get("regime_label", "") or ""),
        context_df=context_df,
        expressions_df=expr_df,
    )
    if distillation.blocked:
        raise RuntimeError(distillation.block_reason)
    idea_votes_section = format_policy_votes_section(distillation)

    advisory_dir = base_dir / "data/advisory"
    advisory_dir.mkdir(parents=True, exist_ok=True)

    advisory_path = advisory_dir / f"{manifest.run_id}_claude_brief.md"
    latest_path = advisory_dir / "latest_claude_brief.md"

    am_required = advisory_payload.get("am_note_required_before_paper", True)
    macro_summary = str(advisory_payload.get("macro_context_summary", ""))
    dealer_summary = str(advisory_payload.get("dealer_positioning_summary", ""))
    catalyst_summary = str(advisory_payload.get("macro_catalyst_summary", ""))
    spread_posture = str(advisory_payload.get("spread_posture", ""))
    pre_am = advisory_payload.get("pre_am_structure", {})
    dealer_struct = advisory_payload.get("dealer_structure", {})

    policy_line = (
        "Macro context may be incomplete; hydration and expression search continue. "
        "Missing or unparsed AM Founder note does not hard-block the morning run. "
        "Credential gaps park hydration only. Paper approval is not trade selection."
    )
    readiness = advisory_payload.get("run_readiness", {})
    if not isinstance(readiness, dict):
        readiness = {}
    macro_lane = readiness.get("macro", {}) if isinstance(readiness.get("macro"), dict) else {}
    hydration_lane = (
        readiness.get("hydration", {}) if isinstance(readiness.get("hydration"), dict) else {}
    )
    selection_lane = (
        readiness.get("selection", {}) if isinstance(readiness.get("selection"), dict) else {}
    )
    morning = advisory_payload.get("morning_regime_status", {})
    if not isinstance(morning, dict):
        morning = {}
    no_action_language = ""
    if str(morning.get("paper_action", "")) == "WITHHELD_QUALITY":
        no_action_language = (
            "No paper action. Quality gate withheld selection. "
            "Options were evaluated; no structure met quality requirements. "
            "Morning Regime completed with no-action decision."
        )

    body = f"""# Kidweel Morning Brief

Run ID: `{manifest.run_id}`  
Run status: `{manifest.status}`  
Mode: `{manifest.mode}`

## Macro context gate (AM Founder note)

{policy_line}

| Field | Value |
|-------|-------|
| `am_note_status` | `{advisory_payload.get("am_note_status", "")}` |
| `macro_context_state` | `{advisory_payload.get("macro_context_state", "")}` |
| `paper_gate_macro_status` | `{advisory_payload.get("paper_gate_macro_status", "")}` |
| `am_note_required_before_paper` | `{am_required}` |
| `macro_readiness_status` | `{advisory_payload.get("macro_readiness_status", "")}` |
| `macro_context_source` | `{advisory_payload.get("macro_context_source", "")}` |
| `macro_blocks_run` | `{advisory_payload.get("macro_blocks_run", False)}` |

**Macro context:** {macro_summary}

**Dealer positioning:** {dealer_summary or dealer_struct.get("structure_summary", "")}

**Catalysts:** {catalyst_summary or "(none parsed)"}

**Spread posture:** {spread_posture}

**Pre-AM structure (retained when note arrives):** {pre_am.get("pre_note_advisory_summary", "") if isinstance(pre_am, dict) else ""}

Dealer structure bias (pre-AM): `{dealer_struct.get("advisory_bias", "") if isinstance(dealer_struct, dict) else ""}`  
Gamma regime: `{dealer_struct.get("gamma_regime", "") if isinstance(dealer_struct, dict) else ""}`

Run advisory JSON: `{run_advisory_result.advisory_json_artifact}`

## Morning Regime status (operator lanes)

- woke: `{morning.get("woke", False)}`
- macro_context: `{morning.get("macro_context", "")}`
- hydration: `{morning.get("hydration", "")}`
- options_discovery: `{morning.get("options_discovery", "")}`
- structure_build: `{morning.get("structure_build", "")}`
- quality_gate: `{morning.get("quality_gate", "")}`
- paper_action: `{morning.get("paper_action", "")}`
- selected_expression: `{morning.get("selected_expression", None)}`
- candidate_count: {morning.get("candidate_count", 0)}
- parked_count: {morning.get("parked_count", 0)}
- rejected_count: {morning.get("rejected_count", 0)}
- top_reasons: {morning.get("top_reasons", [])}
- operator_next_action: `{morning.get("operator_next_action", "")}`

{no_action_language}

## Run readiness (degrade-not-block lanes)

- macro: `{macro_lane.get("status", "")}` / `{macro_lane.get("source", "")}`
- hydration: `{hydration_lane.get("status", "")}` / `{hydration_lane.get("reason", "")}`
- selection: `{selection_lane.get("status", "")}` / `{selection_lane.get("reason", "")}`
- hydration_parked_count: {hydration_lane.get("parked_count", 0)}
- selection_parked_count: {selection_lane.get("parked_count", 0)}

## Intake

- Files found: {manifest.files_found}
- Files staged: {manifest.files_staged}
- Files rejected: {manifest.files_rejected}

## Risk classification (from artifacts)

- Total candidates: {summary.get("total_candidates", 0)}
- Approved (paper-only review): {summary.get("approved_paper_only", 0)}
- Paper gate withheld (AM note): {summary.get("paper_gate_withheld_am_note", 0)}
- Paper gate withheld (frontier review): {summary.get("paper_gate_withheld_frontier", 0)}
- Parked for review: {summary.get("parked", 0)}
- Reverse-vrp symbol context rows: {summary.get("reverse_vrp_symbol_context_rows", 0)}
- Context gate rejects: {summary.get("context_gate_rejects", 0)}
- SPY backdrop absent (advisory only): {summary.get("spy_backdrop_absent", 0)}
- Context gamma source absent (VRP-only, not a spread reject): {summary.get("context_gamma_source_absent", 0)}

## Hydration loop (capability lanes, not new agents)

- Hydration pending: {summary.get("hydration_pending", 0)}
- Parked data gap: {summary.get("parked_data_gap", 0)}
- No viable expression: {summary.get("no_viable_expression", 0)}
- Primary expression selected: {summary.get("primary_expression_selected", 0)}
- Watch expression available: {summary.get("watch_expression_available", 0)}
- Watch operator review pending: {summary.get("watch_operator_review", 0)}
- Watch operator approved: {summary.get("watch_operator_approved", 0)}
- Watch operator rejected: {summary.get("watch_operator_rejected", 0)}
- Alternates available: {summary.get("alternates_available", 0)}
- Hydration expressions attempted: {summary.get("hydration_expressions_attempted", 0)}
- Expression count (total): {expr_summary.get("expression_count_total", 0)}
- Primary expressions: {expr_summary.get("primary_expression_count", 0)}
- Alternate expressions: {expr_summary.get("alternate_expression_count", 0)}
- Watch expressions: {expr_summary.get("watch_expression_count", 0)}
- Failed expressions: {expr_summary.get("failed_expression_count", 0)}
- Dealer tier A: {expr_summary.get("dealer_tier_a", 0)}
- Dealer tier B: {expr_summary.get("dealer_tier_b", 0)}
- Dealer tier C: {expr_summary.get("dealer_tier_c", 0)}
- Dealer tier D: {expr_summary.get("dealer_tier_d", 0)}
- Dealer tier E: {expr_summary.get("dealer_tier_e", 0)}

### Top loop / context reasons

{_format_reasons(list(summary.get("top_rejection_reasons", [])))}

### Context fields (artifact-sourced)

- Regime label: `{summary.get("regime_label", "")}`
- Structure bias: `{summary.get("structure_bias", "")}`

## Expression frontier review

Selected is not optimal. Attractive is not approved.

Frontier review required: `{advisory_payload.get("frontier_review_required_before_paper", False)}`  
Artifact: `{advisory_payload.get("expression_frontier_artifact", "")}`

{format_expression_frontier_section(frontier_summaries)}

## Spread skeptic review

Attractive is not approved. Selected is not optimal. Rejected is not broken.

{format_spread_skeptic_section(skeptic_notes)}

{idea_votes_section}

## Guardrails

- Live mode enabled: `{manifest.live_mode_enabled}`
- Broker mutation occurred: `{manifest.broker_mutation_occurred}`

## Advisory

Context incomplete until the AM Founder note is parsed unless manual override is recorded.
Hydration and expression frontier review may continue; paper approval is withheld when required.

The operator reviews the audit artifact paths below.

No live execution path was enabled.

## Artifact paths

- Context: `{manifest.context_artifact}`
- Candidates: `{manifest.candidates_artifact}`
- Expressions: `{manifest.expressions_artifact}`
- Risk audit: `{manifest.risk_audit_artifact}`
"""

    advisory_path.write_text(body, encoding="utf-8")
    latest_path.write_text(body, encoding="utf-8")

    return ClaudeBriefResult(advisory_artifact=str(advisory_path))
