# SpotGamma → replay candidates (SG-BT-C2)

## Purpose

**Candidate staging only.** Converts normalized SpotGamma **context** rows (SG-BT-C1A) into **replay candidate** rows with optional same-date **SPY market context** attached.

This is **not**:

- Historical trade replay
- Alpaca option-chain or bar join
- `ReplayContext` construction
- Trade approval, playbook selection, PnL, or execution
- MCP or broker I/O

## Inputs

- `data/processed/spotgamma_context_sample.csv` (from `examples/spotgamma_replay_corpus.py`), **or**
- In-memory rebuild via committed ingest (`build_context_corpus(..., include_raw=True)`) when CSV is missing and `--include-raw` is set

## Profile handling

| `source_profile` | Role in C2 |
|------------------|------------|
| `spy_history` | **Market regime context only** — indexed by `trade_date`, not emitted as candidates |
| `squeeze`, `vrp`, `reverse_vrp`, `processed_weekly` | **Candidate source rows** |

- **SPY is not a universal ticker proxy.** Scanner rows for symbol `SPY` may appear as candidates when they originate from a scanner profile, not from `spy_history`.
- Same-date SPY fields populate `spy_*` columns when a `spy_history` row exists for that `trade_date`; otherwise `has_spy_context=False` and `candidate_reason` includes `+missing_spy_context`.

## Output

- CLI prints counts, date range, profile breakdown, SPY attachment stats, and top missing fields.
- Optional CSV: `data/processed/spotgamma_replay_candidates.csv` (gitignored under `data/`)

## Command

```bash
PYTHONPATH=src python examples/spotgamma_to_replay_candidates.py \
  --input data/processed/spotgamma_context_sample.csv \
  --no-write
```

Rebuild context when sample CSV is absent:

```bash
PYTHONPATH=src python examples/spotgamma_to_replay_candidates.py --include-raw --no-write
```

## Next packet

Join candidates to Alpaca historical option chain / bars to build replay-ready structures. Out of scope for SG-BT-C2.

## Module

`src/qops/backtest/spotgamma_replay_builder.py` — `build_replay_candidates`, CSV load, summaries.
