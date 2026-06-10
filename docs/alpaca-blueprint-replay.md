# Alpaca blueprint replay inputs (SG-BT-C4A)

## Purpose

Adapt the [Alpaca 0DTE options backtesting example](https://github.com/alpacahq/alpaca-py/tree/e4268eb61c564b0b665fa32f69024a9970e6f12b/examples/options/options-zero-dte-backtesting) **shape** into Kidweel’s SpotGamma replay pipeline:

- collect option symbols by expiration (planned, not fetched here)
- limit candidates by underlying, trade date, and DTE
- fetch only required chains/bars (described for a future read-only packet)
- preserve a minimal query surface
- stop before `ReplayContext` or PnL

SpotGamma narrows the universe **before** any option data request. Fewest rows possible is a hard rule: no full OPRA surface, no bulk Databento pulls, no entire-universe scans.

**Option Alpha spread math** (`qops.strategy.spread_math`, PMP min R/R table) is the required **expression gate later**—after contracts are narrowed and economics exist. C4A does not run STRUCT-MATH or select strategy legs.

**SG-BT-C4A scope:** multi-leg structures remain canonical policy (`BULL_CALL_SPREAD`, `BEAR_PUT_SPREAD`, credit spreads when implemented). This packet does not pick legs; if a future fetch packet conflicts with four-structure breadth, the evidence track may start with **BULL_CALL_SPREAD** only without changing canonical policy. No fallback was required for C4A.

This packet does **not** generate trades, execution payloads, or PnL. It does **not** call MCP or paper transport.

## Upstream

SG-BT-C3 produces `alpaca_replay_input_plan.csv` with `READY_FOR_FETCH` rows when symbol, trade date, `current_price`, and SPY context are present.

```bash
PYTHONPATH=src python examples/alpaca_replay_input_availability.py --rebuild-if-missing --no-write
```

## Blueprint request plan

```bash
PYTHONPATH=src python examples/alpaca_blueprint_replay_inputs.py \
  --input data/processed/alpaca_replay_input_plan.csv \
  --rebuild-if-missing \
  --dte-min 0 \
  --dte-max 7 \
  --strike-buffer-pct 0.03 \
  --limit 50 \
  --no-write
```

Output (optional, gitignored under `data/`):

```bash
--output data/processed/alpaca_blueprint_replay_plan.csv
```

### Behavior

1. Load **READY_FOR_FETCH** rows only.
2. Group by `symbol` and `trade_date`.
3. Build a minimal option-chain request plan using a configurable DTE window (`expiration_window`).
4. Estimate a conservative strike band around SpotGamma `current_price` (`strike_buffer_pct`).
5. Emit an option symbol **request plan** (OCC symbols are resolved in a later Alpaca read-only fetch packet).
6. **No Databento fetch** in C4A.

### Databento entry point (later)

After Alpaca read-only chain collection returns OCC symbols inside `expiration_window` and strike bounds, a future packet may request **Databento Greeks and bar slices for those contracts only**. C4A records this as `databento_next_step` on each plan row.

## Boundaries

- Read-only data planning only
- No order endpoints, MCP transport, paper/live trading
- No bulk OPRA or broad Databento pulls
- No strike selection beyond minimal narrowing around spot
- No `ReplayContext`, no PnL

## Module

`src/qops/backtest/alpaca_blueprint_adapter.py` — load READY rows, group, expiration/strike planning, summaries.
