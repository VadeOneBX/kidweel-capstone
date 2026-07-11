from __future__ import annotations

from pathlib import Path
from typing import Any

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
from qops.advisory.run_readiness import build_operator_next_actions
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


def _format_operator_actions(actions: list[dict[str, str]]) -> str:
    if not actions:
        return "- (none)"
    lines: list[str] = []
    for action in actions:
        lines.append(
            f"- `{action.get('id', '')}`: `{action.get('command', '')}`\n"
            f"  reason: {action.get('reason', '')}\n"
            f"  expected: {action.get('expected_output', '')}"
        )
    return "\n".join(lines)


def format_macro_gate_brief_section(
    *,
    morning_regime_status: dict[str, Any],
    advisory_payload: dict[str, Any],
) -> str:
    """Operator-facing macro gate section; morning_regime_status is canonical."""
    morning = morning_regime_status if isinstance(morning_regime_status, dict) else {}
    audit = advisory_payload.get("macro_context_audit", {})
    if not isinstance(audit, dict):
        audit = {}
    private = advisory_payload.get("private_vendor_context", {})
    if not isinstance(private, dict):
        private = {}
    conf = private.get("parse_confidence") if isinstance(private.get("parse_confidence"), dict) else {}
    sources = private.get("sources") if isinstance(private.get("sources"), dict) else {}
    lanes = private.get("lanes") if isinstance(private.get("lanes"), dict) else {}

    am_required = bool(advisory_payload.get("am_note_required_before_paper", True))
    dealer_summary = str(advisory_payload.get("dealer_positioning_summary", "") or "")
    dealer_struct = advisory_payload.get("dealer_structure", {})
    if not isinstance(dealer_struct, dict):
        dealer_struct = {}
    if not dealer_summary:
        dealer_summary = str(dealer_struct.get("structure_summary", "") or "")
    if not am_required:
        # Never echo legacy "required before paper" copy when the gate does not require it.
        lowered = dealer_summary.lower()
        if "required before paper" in lowered or "still required" in lowered:
            dealer_summary = (
                "Pre-AM note structure recorded from SpotGamma; Founder's Note prose "
                "remains optional low-confidence enrichment."
            )

    catalyst_summary = str(advisory_payload.get("macro_catalyst_summary", "") or "")
    spread_posture = str(advisory_payload.get("spread_posture", "") or "")
    pre_am = advisory_payload.get("pre_am_structure", {})
    if not isinstance(pre_am, dict):
        pre_am = {}

    canonical_macro = str(morning.get("macro_context", "") or "")
    policy_line = (
        "**Macro context is advisory.** Founder's Note / AM-note gaps degrade confidence "
        "and emit warnings; they do not block the morning loop. Structured sidecars remain "
        "preferred. Private macro lanes and morning_regime_status remain authoritative. "
        "Alpaca credential errors park hydration separately."
    )

    if canonical_macro == "PARTIAL":
        macro_narrative = (
            "Private macro context is PARTIAL.\n"
            "AM-note / Founder's Note prose remains missing or incomplete.\n"
            "Morning loop continues with degraded macro confidence."
        )
    elif canonical_macro in {"READY", "READY_LOW_CONFIDENCE"}:
        macro_narrative = str(advisory_payload.get("macro_context_summary", "") or "")
    elif canonical_macro in {"MISSING_NON_BLOCKING", "UNPARSED_NON_BLOCKING"}:
        macro_narrative = str(advisory_payload.get("macro_context_summary", "") or "")
    else:
        macro_narrative = str(advisory_payload.get("macro_context_summary", "") or "")

    flow_lane = str(morning.get("flow_context") or lanes.get("flow_context") or "")
    flow_conf = str(conf.get("flow_report", "") or "")
    source_date = str(sources.get("source_date", "") or "")
    flow_lines = (
        f"- flow_context (canonical): `{flow_lane}`\n"
        f"- flow parse_confidence: `{flow_conf}`\n"
        f"- private source_date: `{source_date}`"
    )

    return f"""## Macro context gate (private macro note)

{policy_line}

Canonical lane (`morning_regime_status.macro_context`): `{canonical_macro}`

AM-note / Founder's Note prose audit (source split; not a second readiness taxonomy):

| Field | Value |
|-------|-------|
| `am_note_status` | `{advisory_payload.get("am_note_status", "")}` |
| `macro_context_state` | `{advisory_payload.get("macro_context_state", "")}` |
| `paper_gate_macro_status` | `{advisory_payload.get("paper_gate_macro_status", "")}` |
| `am_note_required_before_paper` | `{am_required}` |
| `macro_context_audit.status` | `{audit.get("status", "")}` |
| `macro_context_audit.parse_status` | `{audit.get("parse_status", "")}` |
| `macro_context_audit.source_type` | `{audit.get("source_type", "")}` |

**Macro context:**
{macro_narrative}

**Dealer positioning:** {dealer_summary}

**Catalysts:** {catalyst_summary or "(none parsed)"}

**Spread posture:** {spread_posture}

**Pre-AM structure (retained when note arrives):** {pre_am.get("pre_note_advisory_summary", "")}

Dealer structure bias (pre-AM): `{dealer_struct.get("advisory_bias", "")}`  
Gamma regime: `{dealer_struct.get("gamma_regime", "")}`

### Flow lane (private)

{flow_lines}
"""


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
    tier3_ideas = load_tier3_ideas(base_dir, manifest.run_date, manifest.run_id)
    distillation = distill_subagent_ideas(
        tier3_ideas,
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

    morning = advisory_payload.get("morning_regime_status", {})
    if not isinstance(morning, dict):
        morning = {}
    private = advisory_payload.get("private_vendor_context", {})
    if not isinstance(private, dict):
        private = {}

    actions_raw = morning.get("operator_next_actions")
    if isinstance(actions_raw, list) and actions_raw:
        actions = [a for a in actions_raw if isinstance(a, dict)]
    else:
        actions = build_operator_next_actions(
            morning=morning,
            private_vendor_context=private,
            stored_morning=morning,
        )
    next_action_display = morning.get("operator_next_action") or "; ".join(
        f"{a['id']}: {a['command']}" for a in actions if a.get("command")
    )

    no_action_language = ""
    if str(morning.get("paper_action", "")) == "WITHHELD_QUALITY":
        no_action_language = (
            "No paper action. Quality gate withheld selection. "
            "Options were evaluated; no structure met quality requirements. "
            "Morning Regime completed with no-action decision."
        )

    macro_section = format_macro_gate_brief_section(
        morning_regime_status=morning,
        advisory_payload=advisory_payload,
    )

    body = f"""# Kidweel Morning Brief

Run ID: `{manifest.run_id}`  
Run status: `{manifest.status}`  
Mode: `{manifest.mode}`

{macro_section}

Run advisory JSON: `{run_advisory_result.advisory_json_artifact}`

## Morning Regime status (operator lanes)

- woke: `{morning.get("woke", False)}`
- macro_context: `{morning.get("macro_context", "")}`
- flow_context: `{morning.get("flow_context", "")}`
- skew_context: `{morning.get("skew_context", "")}`
- vol_context: `{morning.get("vol_context", "")}`
- index_levels_context: `{morning.get("index_levels_context", "")}`
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
- operator_next_action: `{next_action_display}`

### Operator next actions (exact commands)

{_format_operator_actions(actions)}

{no_action_language}

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

### Hydration operator commands

{_format_operator_actions([a for a in actions if a.get("id") in {
    "diagnose_quote_hydration",
    "retry_hydration_via_morning_loop",
    "view_readiness",
}])}

### Top loop / context reasons

{_format_reasons(list(summary.get("top_rejection_reasons", [])))}

### Context fields (artifact-sourced)

- Regime label: `{summary.get("regime_label", "")}`
- Structure bias: `{summary.get("structure_bias", "")}`

## Expression frontier review

Selected is still reviewed. Attractive is not approved.

Frontier review required: `{advisory_payload.get("frontier_review_required_before_paper", False)}`  
Artifact: `{advisory_payload.get("expression_frontier_artifact", "")}`

{format_expression_frontier_section(frontier_summaries)}

## Spread skeptic review

Attractive is not approved. Selected is still reviewed. Rejected is not broken.

{format_spread_skeptic_section(skeptic_notes)}

{idea_votes_section}

## Guardrails

- Live mode enabled: `{manifest.live_mode_enabled}`
- Broker mutation occurred: `{manifest.broker_mutation_occurred}`

## Advisory

Macro context may be degraded or missing without blocking the morning loop unless safety forbids paper.
Hydration and expression frontier review may continue; quality/no-action taxonomy remains first-class.

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
