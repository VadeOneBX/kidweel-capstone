# Repository classification (CLEAN-C1)

Read-only inventory: **classify** helpers, examples, tests, and fallback references **without deleting** infrastructure. On conflict with runtime behavior, [docs/system-identity.md](./system-identity.md) wins.

| Path | Group | Notes |
|------|-------|-------|
| `src/qops/pipeline/`, `src/qops/risk/guard_runner.py` | **canonical** | Morning decision path |
| `src/qops/strategy/spread_builder.py`, `spread_math` | **canonical** | Spread economics and structure emit set |
| `src/qops/execution/` (paper bridge, payloads) | **canonical** / **safety-critical** | Paper transport; dry-run default |
| `scripts/orb_morning_loop.py` | **canonical** | Primary session runner; no submit |
| `scripts/daily_ingestion_wake.py`, `scripts/operator_status.py` | **canonical** | Intake and inspection |
| `scripts/review_watch_expression.py` | **canonical** | Operator WATCH promotion; no submit |
| `scripts/diagnose_*.sh`, `scripts/reconcile_claude_mcp.sh`, `scripts/audit_branch_reconciliation.sh` | **legacy** / **tooling** | Repo hygiene diagnostics; not trading path |
| `scripts/full_alpaca_qa.sh` | **tooling** | Paper QA; explicit scope only |
| `examples/submit_paper_payload_candidates.py`, `close_paper_position.py` | **canonical** / **safety-critical** | Opt-in paper transport CLIs |
| `examples/build_paper_*`, `check_paper_*` | **canonical** | Payload/approval/status helpers |
| `examples/generate_spread_candidates.py` | **canonical** | Staged greeks → candidates; no transport |
| `examples/spotgamma_*.py`, `alpaca_blueprint_replay_inputs.py` | **canonical** | Replay / corpus / blueprint planning |
| `examples/alpaca_replay_input_availability.py` | **canonical** | SG-BT-C3 availability plan CSV |
| `examples/generate_operator_advisory.py` | **experimental** | Advisory packet helper; non-approving |
| `examples/options-bull-call-spread.ipynb` (if present locally) | **legacy** / **reference** | Alpaca article alignment; see [notebook-alignment.md](./notebook-alignment.md) — not execution authority |
| `src/qops/backtest/runner.py`, `metrics.py`, `summary.py` | **canonical** | Deterministic replay aggregation |
| `src/qops/backtest/overlay_filter.py`, `claude_comparison.py` | **experimental** | Research comparisons; not approval path |
| `src/qops/backtest/alpaca_replay_inputs.py` | **canonical** | Planning stub; historical fetch = future packet |
| `docs/backtests/`, `docs/audit/mock_*`, `docs/reconciliation/mock_*` | **archive** / **labeled mock** | Synthetic inspection memos |
| `docs/evidence_artifacts_guide.md`, `docs/backtest_evidence_status.md` | **canonical** | Evidence and backtest status docs |
| `tests/test_alpaca_paper_bridge.py`, `tests/test_paper_closeout.py` | **safety-critical** | Paper transport contracts |
| `tests/test_*` (remaining) | **canonical** | Regression on gates and pipeline |
| `integrations/alpaca_mcp/` | **canonical** / **tooling** | MCP transport scaffold; repo owns approval |
| `data/processed/`, `data/runs/`, `data/backtests/` | **runtime** (gitignored) | Local evidence; not source of public PnL claims |
| `notebooks/` (search-excluded) | **legacy** | Research notebooks if present; not morning loop |

**Delete-candidate:** none identified in this packet — prefer labels over removal.
