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

Regenerate context after SG-BT-C1A so `source_profile` and raw scanner rows are present. **Stale pre-C1A CSVs** (missing `source_profile` or raw profiles) are **rejected** by the candidate CLI unless you pass `--allow-stale-input` (diagnostics) or `--rebuild-if-stale`.

## Canonical commands

Build fresh context (required for full candidate staging):

```bash
PYTHONPATH=src python examples/spotgamma_replay_corpus.py --include-raw
```

Stage replay candidates from that file:

```bash
PYTHONPATH=src python examples/spotgamma_to_replay_candidates.py \
  --input data/processed/spotgamma_context_sample.csv
```

If you still have a stale sample on disk:

```bash
PYTHONPATH=src python examples/spotgamma_to_replay_candidates.py \
  --input data/processed/spotgamma_context_sample.csv \
  --rebuild-if-stale --no-write
```

- **`--allow-stale-input`** — diagnostics only (e.g. 118 processed_weekly rows, no SPY context).
- **Full candidate staging** requires raw profile context (squeeze / vrp / reverse_vrp / spy_history).

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

## Next packet

Join candidates to Alpaca historical option chain / bars to build replay-ready structures. Out of scope for SG-BT-C2.

## Module

`src/qops/backtest/spotgamma_replay_builder.py` — `build_replay_candidates`, CSV load, summaries.
