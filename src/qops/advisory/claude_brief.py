from __future__ import annotations

from pathlib import Path

import pandas as pd
from pydantic import BaseModel

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
    expressions_path = Path(manifest.expressions_artifact or "")
    if not expressions_path.is_file() and manifest.run_id:
        from qops.pipeline.alpaca_hydration_loop import expressions_artifact_path

        expressions_path = expressions_artifact_path(base_dir, manifest.run_id)
    expr_summary: dict[str, int] = {}
    if expressions_path.is_file():
        expr_df = pd.read_csv(expressions_path)
        if manifest.run_id and "run_id" in expr_df.columns:
            expr_df = expr_df[expr_df["run_id"].astype(str) == str(manifest.run_id)]
        expr_summary = summarize_expression_artifact(expr_df)

    advisory_dir = base_dir / "data/advisory"
    advisory_dir.mkdir(parents=True, exist_ok=True)

    advisory_path = advisory_dir / f"{manifest.run_id}_claude_brief.md"
    latest_path = advisory_dir / "latest_claude_brief.md"

    body = f"""# Kidweel Morning Brief

Run ID: `{manifest.run_id}`  
Run status: `{manifest.status}`  
Mode: `{manifest.mode}`

## Intake

- Files found: {manifest.files_found}
- Files staged: {manifest.files_staged}
- Files rejected: {manifest.files_rejected}

## Risk classification (from artifacts)

- Total candidates: {summary.get("total_candidates", 0)}
- Approved (paper-only review): {summary.get("approved_paper_only", 0)}
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

## Guardrails

- Live mode enabled: `{manifest.live_mode_enabled}`
- Broker mutation occurred: `{manifest.broker_mutation_occurred}`

## Advisory

Market context has been established from deterministic ingestion artifacts.

The risk guard classified the candidate set.

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
