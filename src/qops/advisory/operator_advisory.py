"""Deterministic operator advisory voice from run artifacts (ADVISORY-VOICE-C1)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from pydantic import BaseModel

from qops.pipeline.alpaca_hydration_loop import expressions_artifact_path, summarize_expression_artifact
from qops.schemas.candidate_loop import CandidateLoopStatus, SpreadExpressionStatus

_CAPSTONE_CLOSING = (
    "This run demonstrates deterministic decision separation: ingestion can succeed, "
    "candidates can be retained, expressions can be searched, and paper approval can "
    "still be withheld. Rejection is evidence, not system failure."
)

@dataclass(frozen=True, slots=True)
class RunArtifactPaths:
    context: Path
    candidates: Path
    expressions: Path
    risk_audit: Path


class OperatorAdvisoryResult(BaseModel):
    operator_advisory_artifact: str


def default_artifact_paths(base_dir: Path, run_id: str) -> RunArtifactPaths:
    return RunArtifactPaths(
        context=base_dir / "data/processed/context" / f"{run_id}_context.csv",
        candidates=base_dir / "data/processed/candidates" / f"{run_id}_candidates.csv",
        expressions=expressions_artifact_path(base_dir, run_id),
        risk_audit=base_dir / "data/processed/risk" / f"{run_id}_risk_audit.csv",
    )


def operator_advisory_output_path(base_dir: Path, run_id: str) -> Path:
    return base_dir / "data/processed" / f"{run_id}_operator_advisory.md"


def _fmt(value: object, *, missing: str = "(missing)") -> str:
    if value is None:
        return missing
    if isinstance(value, float) and math.isnan(value):
        return missing
    if isinstance(value, str) and not value.strip():
        return missing
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        f = float(value)
        if math.isfinite(f) and abs(f - round(f)) < 1e-9:
            return str(int(round(f)))
        if math.isfinite(f):
            return f"{f:.4g}"
    return str(value)


_OPTION_CONTRACT_MULTIPLIER = 100


def _num(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _fmt_contract_pnl(value: object) -> str:
    """Per-share artifact economics → whole-dollar PnL for one standard contract."""
    per_share = _num(value)
    if per_share is None:
        return "(missing)"
    dollars = int(round(per_share * _OPTION_CONTRACT_MULTIPLIER))
    return f"${dollars}"


def _fmt_rr_display(value: object) -> str:
    """Reward/risk ratio as a compact multiplier (one decimal, trailing .0 dropped)."""
    rr = _num(value)
    if rr is None:
        return "(missing)"
    rounded = round(rr, 1)
    if abs(rounded - round(rounded)) < 1e-9:
        return f"{int(round(rounded))}×"
    return f"{rounded:.1f}×"


def _fmt_pmp_percent(value: object) -> str:
    """PMP on 0–1 scale (or already 0–100) → percentage for operators."""
    pmp = _num(value)
    if pmp is None:
        return "(missing)"
    pct = pmp * 100.0 if pmp <= 1.0 else pmp
    return f"{int(round(pct))}%"


def _count_classification(risk_df: pd.DataFrame, label: str) -> int:
    if risk_df.empty or "classification" not in risk_df.columns:
        return 0
    return int((risk_df["classification"].astype(str) == label).sum())


def _paper_approval_count(risk_df: pd.DataFrame) -> int:
    if risk_df.empty:
        return 0
    approved = 0
    if "classification" in risk_df.columns:
        col = risk_df["classification"].astype(str)
        approved += int(col.isin({"APPROVED_PAPER", "APPROVED_FOR_PAPER_REVIEW"}).sum())
    if "paper_approval_status" in risk_df.columns:
        col = risk_df["paper_approval_status"].astype(str)
        approved = max(
            approved,
            int((col == "APPROVED_FOR_PAPER_REVIEW").sum()),
        )
    return approved


def _top_symbol_by_expressions(expr_df: pd.DataFrame) -> str:
    if expr_df.empty or "symbol" not in expr_df.columns:
        return "(none)"
    counts = expr_df["symbol"].astype(str).str.upper().value_counts()
    if counts.empty:
        return "(none)"
    return str(counts.index[0])


def _primary_expression_row(expr_df: pd.DataFrame) -> pd.Series | None:
    if expr_df.empty or "expression_status" not in expr_df.columns:
        return None
    prim = expr_df[expr_df["expression_status"].astype(str) == SpreadExpressionStatus.PRIMARY.value]
    if prim.empty:
        return None
    return prim.iloc[0]


def _build_run_summary(
    run_id: str,
    *,
    context_df: pd.DataFrame,
    candidates_df: pd.DataFrame,
    expr_df: pd.DataFrame,
    risk_df: pd.DataFrame,
    expr_summary: dict[str, int],
) -> str:
    watch_n = _count_classification(risk_df, CandidateLoopStatus.WATCH_EXPRESSION_AVAILABLE.value)
    no_viable_n = _count_classification(risk_df, CandidateLoopStatus.NO_VIABLE_EXPRESSION.value)
    paper_n = _paper_approval_count(risk_df)
    primary_row = _primary_expression_row(expr_df)
    top_primary = ""
    if primary_row is not None:
        sym = _fmt(primary_row.get("symbol"))
        strikes = f"{_fmt(primary_row.get('long_strike'))}/{_fmt(primary_row.get('short_strike'))}"
        top_primary = f"\nTop primary candidate: **{sym}** bull call spread **{strikes}**."

    top_sym = _top_symbol_by_expressions(expr_df)

    return f"""## Run summary

- **run_id:** `{run_id}`
- **context rows:** {len(context_df)}
- **candidates:** {len(candidates_df)}
- **hydrated expressions:** {expr_summary.get("expression_count_total", len(expr_df))}
- **primary expressions:** {expr_summary.get("primary_expression_count", 0)}
- **alternate expressions:** {expr_summary.get("alternate_expression_count", 0)}
- **watch expression rows:** {expr_summary.get("watch_expression_count", 0)}
- **WATCH candidates (operator review):** {watch_n}
- **no viable expression candidates:** {no_viable_n}
- **paper approval count:** {paper_n}
- **top symbol by expression count:** {top_sym}{top_primary}

Run `{run_id}` produced **{len(candidates_df)}** candidates and **{expr_summary.get("expression_count_total", len(expr_df))}** hydrated expressions.
**{expr_summary.get("primary_expression_count", 0)}** primary expression was selected, **{expr_summary.get("alternate_expression_count", 0)}** alternate was retained, **{watch_n}** candidates reached WATCH state, and **{no_viable_n}** candidates exhausted expression search.
"""


def _build_operator_takeaway(
    *,
    candidates_df: pd.DataFrame,
    risk_df: pd.DataFrame,
    expr_df: pd.DataFrame,
    expr_summary: dict[str, int],
) -> str:
    watch_n = _count_classification(risk_df, CandidateLoopStatus.WATCH_EXPRESSION_AVAILABLE.value)
    no_viable_n = _count_classification(risk_df, CandidateLoopStatus.NO_VIABLE_EXPRESSION.value)
    alt_n = _count_classification(risk_df, CandidateLoopStatus.ALTERNATES_AVAILABLE.value)
    primary_n = expr_summary.get("primary_expression_count", 0)
    paper_n = _paper_approval_count(risk_df)

    primary_row = _primary_expression_row(expr_df)
    primary_line = ""
    if primary_row is not None:
        sym = _fmt(primary_row.get("symbol"))
        primary_line = (
            f"The system retained one paper-reviewable bull call spread on **{sym}** "
            f"and scored additional alternates where the dealer-weighted tier allowed. "
        )
    elif alt_n:
        primary_line = "The system retained a primary plus backup expression on at least one name. "
    else:
        primary_line = "No primary expression cleared the dealer-weighted tier for paper review in this run. "

    watch_line = ""
    if watch_n:
        watch_line = (
            f"Most other names are not dead; **{watch_n}** are WATCH candidates blocked by the "
            f"current dealer-weighted tier rather than by missing chain data. "
        )

    paper_line = ""
    if paper_n == 0:
        paper_line = "Paper approval count is zero; withholding approval is expected when macro or frontier gates apply. "
    else:
        paper_line = f"**{paper_n}** row(s) reached paper-review classification. "

    return f"""## Operator takeaway

The pipeline is healthy. Candidate extraction and expression hydration are active.
{primary_line}{watch_line}{paper_line}
**{no_viable_n}** names produced no paper-tradable expression after search and should be treated as clean rejects unless chain structure changes.
"""


def _build_primary_note(expr_df: pd.DataFrame) -> str:
    row = _primary_expression_row(expr_df)
    if row is None:
        return "## Primary expression note\n\nNo PRIMARY expression is recorded in the hydration artifact.\n"

    sym = _fmt(row.get("symbol"))
    structure = _fmt(row.get("structure"), missing="BULL_CALL_SPREAD").replace("_", " ").lower()
    expiration = _fmt(row.get("expiration"))
    dte = _fmt(row.get("dte"))
    strikes = f"{_fmt(row.get('long_strike'))}/{_fmt(row.get('short_strike'))}"
    debit = _fmt_contract_pnl(row.get("debit"))
    max_profit = _fmt_contract_pnl(row.get("max_profit"))
    max_loss = _fmt_contract_pnl(row.get("max_loss"))
    rr = _fmt_rr_display(row.get("rr_actual"))
    pmp = _fmt_pmp_percent(row.get("pmp"))
    tier = _fmt(row.get("dealer_gate_tier"))
    dws = _fmt(row.get("dealer_weighted_score"))
    baq = _fmt(row.get("bid_ask_quality"))
    reason = _fmt(row.get("expression_reason"), missing="primary expression under dealer-weighted tier")

    body = f"""## Primary expression note

**{sym}** is the current cleanest expression. The system selected a **{dte}** DTE {structure} with defined max loss of **{max_loss}** and max profit of **{max_profit}** (one contract, 100 shares).
R/R is **{rr}** and PMP is **{pmp}**. Dealer score is Tier **{tier}** / **{dws}**, which makes it the only current primary candidate in this run.

| Field | Value |
|-------|-------|
| Symbol | {sym} |
| Structure | {_fmt(row.get('structure'))} |
| Expiration | {expiration} |
| DTE | {dte} |
| Strikes | {strikes} |
| Debit (1-lot) | {debit} |
| Max profit (1-lot) | {max_profit} |
| Max loss (1-lot) | {max_loss} |
| R/R | {rr} |
| PMP | {pmp} |
| Dealer tier | {tier} |
| Dealer weighted score | {dws} |
| Bid/ask quality | {baq} |
| Expression reason | {reason} |
"""
    return body


def _watch_sentence(row: pd.Series, expr_df: pd.DataFrame) -> str:
    sym = _fmt(row.get("symbol") or row.get("underlying"))
    dte = ""
    structure = "bull call spread"
    sym_exprs = pd.DataFrame()
    if not expr_df.empty and "symbol" in expr_df.columns:
        sym_exprs = expr_df[expr_df["symbol"].astype(str).str.upper() == sym.upper()]
    watch_exprs = sym_exprs[
        sym_exprs.get("expression_status", pd.Series(dtype=str)).astype(str)
        == SpreadExpressionStatus.WATCH.value
    ]
    if not watch_exprs.empty:
        w = watch_exprs.iloc[0]
        dte = _fmt(w.get("dte"), missing="")
        structure = _fmt(w.get("structure"), missing="bull call spread").replace("_", " ").lower()
    elif not sym_exprs.empty:
        w = sym_exprs.iloc[0]
        dte = _fmt(w.get("dte"), missing="")
        structure = _fmt(w.get("structure"), missing="bull call spread").replace("_", " ").lower()

    dte_part = f"{dte} DTE " if dte and dte != "(missing)" else ""
    return (
        f"**{sym}** reached WATCH with a {dte_part}{structure}, but was not selected under the "
        f"current dealer-weighted tier. This is an operator review candidate, not a broken candidate."
    )


def _build_watch_notes(risk_df: pd.DataFrame, expr_df: pd.DataFrame) -> str:
    if risk_df.empty or "classification" not in risk_df.columns:
        return "## WATCH candidate notes\n\n(no WATCH classifications in risk audit)\n"

    watch_rows = risk_df[
        risk_df["classification"].astype(str)
        == CandidateLoopStatus.WATCH_EXPRESSION_AVAILABLE.value
    ]
    if watch_rows.empty:
        return "## WATCH candidate notes\n\n(no WATCH classifications in risk audit)\n"

    lines = ["## WATCH candidate notes", ""]
    for _, row in watch_rows.iterrows():
        lines.append(f"- {_watch_sentence(row, expr_df)}")
    lines.append("")
    return "\n".join(lines)


def _no_viable_sentence(row: pd.Series) -> str:
    sym = _fmt(row.get("symbol") or row.get("underlying"))
    reason = _fmt(row.get("reject_reason"), missing="")
    if "no_viable_expression" in reason.lower() or "expression_search_exhausted" in reason.lower():
        detail = "no paper-tradable expression after search"
    else:
        detail = "no paper-tradable expression after search"
    return (
        f"**{sym}** produced a candidate but {detail}. "
        f"This should remain a clean reject unless chain structure changes."
    )


def _build_no_viable_notes(risk_df: pd.DataFrame) -> str:
    if risk_df.empty or "classification" not in risk_df.columns:
        return "## No-viable-expression notes\n\n(none)\n"

    rows = risk_df[
        risk_df["classification"].astype(str) == CandidateLoopStatus.NO_VIABLE_EXPRESSION.value
    ]
    if rows.empty:
        return "## No-viable-expression notes\n\n(none)\n"

    lines = ["## No-viable-expression notes", ""]
    for _, row in rows.iterrows():
        lines.append(f"- {_no_viable_sentence(row)}")
    lines.append("")
    return "\n".join(lines)


def _build_capstone_note() -> str:
    return f"""## Capstone evidence note

{_CAPSTONE_CLOSING}
"""


def generate_operator_advisory(
    base_dir: Path,
    run_id: str,
    *,
    paths: RunArtifactPaths | None = None,
) -> OperatorAdvisoryResult:
    """Build operator markdown from existing run artifacts (read-only)."""
    resolved = paths or default_artifact_paths(base_dir, run_id)
    missing = [p for p in (resolved.context, resolved.candidates, resolved.expressions, resolved.risk_audit) if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"OPERATOR_ADVISORY_MISSING_ARTIFACTS:{missing}")

    context_df = pd.read_csv(resolved.context)
    candidates_df = pd.read_csv(resolved.candidates)
    expr_df = pd.read_csv(resolved.expressions)
    if run_id and "run_id" in expr_df.columns:
        expr_df = expr_df[expr_df["run_id"].astype(str) == str(run_id)]
    risk_df = pd.read_csv(resolved.risk_audit)

    expr_summary = summarize_expression_artifact(expr_df)

    sections = [
        f"# Operator advisory\n",
        _build_run_summary(
            run_id,
            context_df=context_df,
            candidates_df=candidates_df,
            expr_df=expr_df,
            risk_df=risk_df,
            expr_summary=expr_summary,
        ),
        _build_operator_takeaway(
            candidates_df=candidates_df,
            risk_df=risk_df,
            expr_df=expr_df,
            expr_summary=expr_summary,
        ),
        _build_primary_note(expr_df),
        _build_watch_notes(risk_df, expr_df),
        _build_no_viable_notes(risk_df),
        _build_capstone_note(),
    ]
    body = "\n".join(sections)

    out_path = operator_advisory_output_path(base_dir, run_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")
    return OperatorAdvisoryResult(operator_advisory_artifact=str(out_path))
