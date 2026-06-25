# Backtest evidence

Kidweel maintains **two complementary evidence tracks**. Neither submits orders, calls live endpoints, or relaxes gates.

## BT-C3 — Canonical evidence refresh (primary credibility path)

Aggregates **local staged CSVs** when present: greeks staging, spread candidates, approval/payload readiness, and SpotGamma replay context. Output is classified explicitly (`PAPER_LIVE_EVIDENCE`, `HISTORICAL_REPLAY_EVIDENCE`, `STRUCTURE_EVIDENCE_ONLY`, `FIXTURE_EVIDENCE`, `INCOMPLETE_MISSING_DATA`) and summarized **per class**.

```bash
PYTHONPATH=src python examples/run_canonical_backtest_refresh.py --no-write
```

See [canonical-backtest-refresh.md](./canonical-backtest-refresh.md).

**Honesty:** Historical exit PnL is reported only when declared on input rows (`realized_pnl` or explicit exit price fields). Structure-only rows are not trade outcomes. Missing PMP and missing exits are counted, not filled in.

## THRESH-C1 — Threshold sensitivity sweep

Measures how many staged spread candidates remain **eligible_for_trade_review** under stricter hypothetical floors (reward/risk, EV, bid/ask width)—without changing canonical gates.

```bash
PYTHONPATH=src python examples/run_threshold_sweep.py --no-write
```

See [threshold-sweep.md](./threshold-sweep.md).

## BT-C1 — Deterministic fixture replay (validation sample)

Fixed `ReplayContext` fixtures for iterative backtest metrics and `validate_backtest_summary`—expanded sample size without changing decision rules.

```bash
PYTHONPATH=src python examples/backtest_sanity_run.py
```

Optional inclusion in BT-C3 as `FIXTURE_EVIDENCE`:

```bash
PYTHONPATH=src python examples/run_canonical_backtest_refresh.py --no-write --include-fixture-evidence
```

### Sample composition (52 trades, BT-C1)

| Source | Count | Notes |
|--------|------:|-------|
| `seeded_sanity` | 11 | Fixed trades; loosely mirrors the small C13 findings scale |
| `historical_replay_derived` | 0 | No replay CSV corpus checked into this repo |
| `manually_constructed_deterministic` | 41 | Programmatic fixtures with rotated symbols, playbooks, exits, environments |
| **Total** | **52** | ≥30 minimum for validation trade-count gate |

Categories are tracked separately in the runner output; they are **not** merged in reporting.

### Coverage requirements (BT-C1)

- **Exit reasons:** `TP_80`, `STOP`, `TIME_EXIT`, `EXPIRATION_MAX`, `EXPIRATION_LOSS`
- **Playbooks:** `BULL_CALL_SPREAD`, `BEAR_PUT_SPREAD`
- **Environment labels:** multiple `environment_label` strings on `ReplayContext` (not a substitute for live environment re-derivation)

### BT-C1 honesty constraints

- PnL and exit labels are **declared** on each `ReplayContext`; this path does not re-run structure builders or approval gates per trade.
- Metrics may **FAIL** or **WATCH** under `validate_backtest_summary`; that is expected when evidence is expanded without optimization.
- This is not live trading and does not call brokers or MCP transport.

## Output artifacts

**BT-C3:** `canonical_backtest_refresh.csv`, `canonical_backtest_summary.json` (when not using `--no-write`).

**THRESH-C1:** `threshold_sweep_results.csv`, `threshold_sweep_summary.json` (when not using `--no-write`).

**BT-C1:** Console evidence block from `format_evidence_block` via `backtest_sanity_run.py`.
