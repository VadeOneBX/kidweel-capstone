# SpotGamma replay corpus (SG-BT-C1 / C1A)

## Purpose

Real-data bridge from SpotGamma exports to a **replay-staging** context table. No backtests, gate changes, Alpaca chain join, or live execution.

## Export profiles (header-detected)

| Profile | Typical file | Notes |
|---------|----------------|-------|
| `spy_history` | `SPY_history_table_*.csv` | Daily SPY regime context; `regime_label="SPY"`; optional `vrp = 1M IV − 1M RV` |
| `squeeze` | `squeeze.xlsx` | Scanner; header row auto-detected (row 0 vs 1) |
| `vrp` | `vrp.xlsx` | VRP scanner |
| `reverse_vrp` | `reverse-vrp.xlsx` | Same columns as VRP; profile from filename |
| `processed_weekly` | `processed/spotgamma_weekly_*.csv` | Legacy merged weekly export |

Header matching: strip whitespace, normalize NBSP, collapse spaces, case-insensitive. Numeric cells may use apostrophe-prefixed strings. Excel serial dates converted for date-like columns (e.g. Top Gamma Exp).

**Not derived:** `vrp_z`, fabricated `regime_label` (except SPY history), `confidence`. **No SPY proxy** for other tickers.

## Normalized context fields

Core columns: `symbol`, `trade_date`, `source_file`, `source_type`, `source_profile`, `raw_input_date`, metrics (`gamma_ratio`, `vrp`, `vrp_z`, `iv_rank`, squeeze fields), `regime_label`, `confidence`, `notes`, `missing_fields`.

## Commands

Processed weekly only:

```bash
PYTHONPATH=src python examples/spotgamma_replay_corpus.py
```

Processed + raw profiles (SPY history + all session scanners):

```bash
PYTHONPATH=src python examples/spotgamma_replay_corpus.py --include-raw
```

Output default: `data/processed/spotgamma_context_sample.csv` (gitignored).

## Next packet

Join context rows to Alpaca chain/bar data for full replay — out of scope here.

## Modules

| Module | Role |
|--------|------|
| `src/qops/ingest/spotgamma_loader.py` | Profile detection, CSV/XLSX load, parsing helpers |
| `src/qops/ingest/spotgamma_normalize.py` | Context rows, corpus builder, missing-field tracking |
| `examples/spotgamma_replay_corpus.py` | CLI summary + CSV write |
