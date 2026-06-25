# Canonical backtest evidence refresh (BT-C3)

## What this is

This is **not** a full institutional backtest. It is a **canonical evidence refresh** that aggregates whatever **local staged CSVs** exist across Kidweel’s paper-live and replay tracks:

- Alpaca greeks/quote staging
- Math-gated spread candidates (PMP / R/R / EV)
- Paper approval and payload readiness
- SpotGamma replay **context** candidates

Transport, submit, close, and live endpoints are **out of scope**. Advisory groups (`SQUEEZE_CANDIDATES`, `VOLATILITY_RISK_PREMIUM`, `REVERSE_RISK_PREMIUM`) are **metadata / thesis classification only**—deterministic gates decide; Claude and subagents do not approve.

Paper-live proof (fills, audits) remains a **separate** track from historical replay and from structure-only economics.

## Evidence classes (never blended silently)

| Class | Meaning |
|-------|---------|
| `PAPER_LIVE_EVIDENCE` | Staging rows tagged paper-live (`mode`, provenance, or source) |
| `HISTORICAL_REPLAY_EVIDENCE` | Declared `realized_pnl` and/or explicit exit price columns—**not** inferred from spread math |
| `STRUCTURE_EVIDENCE_ONLY` | Spread economics and gates without honest exit PnL (default for historical staging) |
| `FIXTURE_EVIDENCE` | Opt-in BT-C1 `ReplayContext` fixtures (`--include-fixture-evidence`) |
| `INCOMPLETE_MISSING_DATA` | SpotGamma replay context rows without spread economics |

Summaries in JSON and CLI output are **per class** plus global counts that do not mix PnL across classes.

## Honesty constraints

- **Missing exit prices are not invented.** Structure-only rows keep `missing_exit=true` and no `realized_pnl`.
- **Missing PMP is not fabricated.** Rows without `pmp_for_gate` (and no honest proxy in the spread row) count toward `missing_pmp_count`; `candidate_pass` stays false.
- **Structure-only evidence is not trade PnL.** Do not treat `max_profit` / `reward_risk` as realized outcomes.
- Gates and the PMP table are **unchanged** by this packet; the refresh only **reports** pass/fail fields already on staged rows or derived read-only from existing math helpers.

## Prerequisites (local pipeline)

Typical inputs under `data/processed/` (gitignored; may be absent in CI):

1. `alpaca_greeks_candidates.csv` — [examples/alpaca_greeks_candidate_stage.py](../examples/alpaca_greeks_candidate_stage.py)
2. `spread_candidates.csv` — [examples/generate_spread_candidates.py](../examples/generate_spread_candidates.py)
3. `paper_approval_candidates.csv` — [examples/build_paper_approval_candidates.py](../examples/build_paper_approval_candidates.py)
4. `paper_payload_candidates.csv` — [examples/build_paper_payload_candidates.py](../examples/build_paper_payload_candidates.py)
5. `spotgamma_replay_candidates.csv` — [examples/spotgamma_to_replay_candidates.py](../examples/spotgamma_to_replay_candidates.py)

Notebook / quote-mid alignment: [notebook-alignment.md](./notebook-alignment.md).

## CLI

```bash
PYTHONPATH=src python examples/run_canonical_backtest_refresh.py --no-write
```

Flags:

| Flag | Default |
|------|---------|
| `--input-spreads` | `data/processed/spread_candidates.csv` |
| `--input-approvals` | `data/processed/paper_approval_candidates.csv` |
| `--input-payloads` | `data/processed/paper_payload_candidates.csv` |
| `--input-greeks` | `data/processed/alpaca_greeks_candidates.csv` |
| `--input-sg` | `data/processed/spotgamma_replay_candidates.csv` |
| `--output` | `data/processed/canonical_backtest_refresh.csv` |
| `--summary-output` | `data/processed/canonical_backtest_summary.json` |
| `--no-write` | off |
| `--limit` | none |
| `--include-fixture-evidence` | off (BT-C1 fixtures) |
| `--derive-spreads-if-missing` / `--no-derive-spreads-if-missing` | derive in-memory from greeks when spread CSV missing |

## Module

[`src/qops/backtest/canonical_refresh.py`](../src/qops/backtest/canonical_refresh.py) — evidence rows, advisory mapping, spread-delta join from greeks, summary JSON.

## Natural-language questions → summary fields

| Question | Where to look |
|----------|----------------|
| “Show the RR to PMP stats of the squeeze candidates chosen, ranked by spread deltas.” | `top_squeeze_candidates_by_spread_delta`, `rr_pmp_summary`, CSV columns `reward_risk`, `pmp`, `spread_delta`, `advisory_group` |
| “Which evidence rows are structure-only versus historical replay?” | `evidence_class` on each row; `evidence_rows_by_class` and `per_class_summaries` in JSON |
| “Which advisory group produced the most math-valid candidates?” | `advisory_group_counts` + `candidates_passing_math` (filter rows by group in CSV) |
| “Which candidates failed because reward/risk did not pay for PMP?” | `failure_reasons` contains `insufficient_reward_risk_for_probability`; `rr_pmp_summary.insufficient_reward_risk_for_pmp_count` |

## Related

- Threshold sensitivity sweep (THRESH-C1): [threshold-sweep.md](./threshold-sweep.md)
- Fixture replay sample (BT-C1): [backtest-evidence.md](./backtest-evidence.md)
- Spread generation policy: [spread-candidate-generation.md](./spread-candidate-generation.md)
- Advisory stubs: [advisory-group-layer.md](./advisory-group-layer.md), [advisory-group-matrix.md](./advisory-group-matrix.md), [sg-advisory-model.md](./sg-advisory-model.md)
