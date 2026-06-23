# Backtest and replay evidence status (BT-C3)

Kidweel evidence is **operator-run artifacts and deterministic gate outcomes**, not checked-in PnL leaderboards. This doc classifies backtest-related paths so public README language points at current truth.

**Canonical evidence map (broader):** [evidence_artifacts_guide.md](./evidence_artifacts_guide.md).  
**Morning / paper operator record:** [audit/paper_bull_call_c1_evidence.md](./audit/paper_bull_call_c1_evidence.md).

---

## Canonical (current evidence sources)

| Path / module | Role |
|---------------|------|
| `data/runs/<run_date>/*_orb_manifest.json` | Run index; artifact pointers |
| `data/processed/risk/<run_id>_risk_audit.csv` | Accept/reject gate evidence |
| `data/processed/<run_id>_alpaca_hydration_expressions.csv` | Hydration / expression lane |
| `data/advisory/<run_id>_claude_brief.md` | Advisory summary (non-approving) |
| `data/processed/paper_*` audits (when built) | Paper transport / status / closeout |
| `src/qops/backtest/runner.py` | `run_iterative_backtest` — aggregates **ReplayContext** rows supplied by pipeline/replay (no broker loop) |
| `src/qops/backtest/spotgamma_replay_builder.py` | SpotGamma → replay candidate export |
| `examples/spotgamma_to_replay_candidates.py`, `examples/spotgamma_replay_corpus.py` | Operator replay corpus tools |
| `examples/alpaca_replay_input_availability.py` | Plans historical fetch needs (`alpaca_replay_input_plan.csv`) — read-only planning |
| `docs/audit/paper_bull_call_c1_evidence.md` | Documented paper/guard evidence posture (local `data/` paths) |

Local CSVs under `data/processed/` are **gitignored**; claims must cite paths from a manifest or audit doc, not implied repo files.

---

## Fallback / historical (useful, not current truth)

| Path / doc | Notes |
|------------|-------|
| `docs/backtests/mock_squeeze_bull_call_spread_50_trades_C1.md` | Synthetic strikes/PnL for inspection |
| `docs/reconciliation/mock_backtest_reconciliation_C1.md` | Reconciliation of mock memo — `synthetic_mock` |
| `docs/audit/mock_*_C1.md` | Mock context / squeeze / advisor synthesis |
| `docs/claude-backtest-wiring.md`, `docs/findings-c13-claude-context.md` | Research overlay comparisons on replay slices |
| `src/qops/backtest/overlay_filter.py`, `claude_comparison.py` | Claude-informed slice comparisons — advisory research only |

Treat Sharpe/PnL from mock memos as **labeled synthetic**, not edge proof.

---

## Stale / misleading (do not cite as evidence)

| Item | Action |
|------|--------|
| External `alpaca_iterative_backtester.py` (not in repo) | **Legacy/scaffold** — random or placeholder Sharpe/PnL |
| Artifacts named like `iterative_results_distribution`, `final_kill_list` | Not present in repo; if found locally, quarantine and do not reference in docs |
| `data/backtests/` (gitignored) | Local scratch only — not canonical |

There is **no** checked-in canonical backtest results directory. Replay aggregation reads **candidate-supplied** context rows.

---

## Evidence language (public)

Emphasize:

- Replay candidates and guard **outcomes** (including rejects and `SKIP`)
- Paper transport **status** when an explicit paper packet ran (dry-run default)
- Deterministic **audit trail** (`reject_reason`, classifications, manifests)
- **No live execution** and no claim that mock memos represent realized PnL

---

## Related implementation docs

- [spotgamma-to-replay.md](./spotgamma-to-replay.md)
- [alpaca-replay-inputs.md](./alpaca-replay-inputs.md) (SG-BT-C3 planning; fetch is a future packet)
- [alpaca-blueprint-replay.md](./alpaca-blueprint-replay.md)
