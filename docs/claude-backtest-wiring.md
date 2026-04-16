# Claude backtest wiring (research only)

Claude file ingestion and re-observation outputs are treated as **research context** for backtest replay and reporting. They do not participate in production approval, risk, execution, or MCP behavior.

**Claude remains non-authoritative.** This packet introduces **research comparisons only**—counterfactual and diagnostic slices over the same deterministic replay inputs. No production approval or execution changes occur here.

Claude context is evaluated as a research filter before it is considered for any bounded operational influence.

## Two-pass workflow

1. **File-native ingestion** — Claude-normalized fields (`file_regime_label`, `file_confidence`, `notes`, pipeline `source_type`) describe what the file snapshot implies without mutating canonical structure or evaluation objects.
2. **Context-adjusted re-observation** — Optional session notes (`session_reliability_state`, `context_note`, `confidence_adjustment_note`, `classification_note`) record how the live session relates to the file; these inform research filters and log columns only.

## What is wired

- **`ClaudeCandidateContext`** — Immutable backtest-side object attached optionally on `ReplayContext.claude_context`.
- **Trade log columns** — Claude fields are persisted on `BacktestTradeLogRow` when context is present; realized PnL and trade outcomes are unchanged.
- **Comparison modes** — `filter_contexts_by_claude_context` and `run_claude_context_comparison` reuse `run_iterative_backtest` to compare baseline vs Claude-informed slices (exclude materially changed, exclude weakened or worse, Claude-only).
- **Evidence** — `format_evidence_block(..., claude_comparison=...)` appends a compact “Claude Context Comparison” section when a comparison dict is supplied.

## Rules

- Claude context may **not** change approval, RR, PMP, execution payloads, or MCP requests.
- Comparison modes are **non-operational**; they do not reclassify raw backtest truth or rewrite realized outcomes.
