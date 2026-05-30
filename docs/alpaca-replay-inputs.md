# Alpaca historical replay inputs (SG-BT-C3)

## Purpose

Answer: **Can each SpotGamma replay candidate be historically priced?**

This packet builds an **availability plan** describing read-only Alpaca data that a future join would need (underlying bars, option chain snapshot, option bars). It does **not** fetch data by default.

This is **not**:

- Execution, paper trading, or MCP
- Order, position, or live trading endpoints
- `ReplayContext` generation
- Trade approval, playbook selection, or strategy tuning
- Fabricated option prices or contract/strike selection

## Upstream workflow

```bash
PYTHONPATH=src python examples/spotgamma_replay_corpus.py --include-raw
PYTHONPATH=src python examples/spotgamma_to_replay_candidates.py \
  --input data/processed/spotgamma_context_sample.csv
```

## Availability planning

```bash
PYTHONPATH=src python examples/alpaca_replay_input_availability.py \
  --input data/processed/spotgamma_replay_candidates.csv \
  --no-write
```

If the candidates CSV is missing:

```bash
PYTHONPATH=src python examples/alpaca_replay_input_availability.py \
  --rebuild-if-missing --no-write
```

Optional output (gitignored under `data/`):

```bash
--output data/processed/alpaca_replay_input_plan.csv
```

DTE window defaults: `--dte-min 0 --dte-max 7`. Entry window assumption: **09:45–15:00 ET** (skip first 30 minutes and last 60 minutes of the regular session).

## `availability_status` values

| Status | Meaning |
|--------|---------|
| `READY_FOR_FETCH` | Symbol, trade date, and current price present; SPY context attached |
| `MISSING_PRICE` | No `current_price` on candidate |
| `MISSING_TRADE_DATE` | No trade date |
| `MISSING_SYMBOL` | No symbol |
| `MISSING_CONTEXT` | Candidate lacks same-date SPY market context |
| `SKIPPED` | Reserved for future explicit skips |

## `--fetch`

Not implemented in SG-BT-C3. A **future packet** may perform read-only historical Alpaca data fetch and join — still no orders or execution.

## Module

`src/qops/backtest/alpaca_replay_inputs.py` — plan builder, summaries, CSV load/rebuild helpers.
