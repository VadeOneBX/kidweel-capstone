# Alpaca greeks layer (ALPACA-GREEKS-C1)

## Purpose

Alpaca-first greeks staging for **paper-trade candidate selection** (not historical replay precision).

For each narrowed SG-BT-C4A blueprint row:

1. Prefer **Alpaca option chain snapshot greeks** when present.
2. Fall back to **Black–Scholes / BSM** greeks only when `--allow-bs-fallback` is set and IV (or an explicit `--fallback-volatility-proxy`) is available.
3. Record `greeks_source`, `greeks_status`, and `greeks_confidence` on every contract row.

## Upstream

- Input: `data/processed/alpaca_blueprint_replay_plan.csv`, or rebuild via C4A (`--rebuild-if-missing`).
- SpotGamma → C3 availability → C4A blueprint strike/DTE window.

## CLI

Dry-run (default — no network):

```bash
PYTHONPATH=src python examples/alpaca_greeks_candidate_stage.py \
  --rebuild-if-missing \
  --no-write \
  --limit 10
```

Read-only Alpaca fetch (requires market data credentials in the environment):

```bash
PYTHONPATH=src python examples/alpaca_greeks_candidate_stage.py \
  --rebuild-if-missing \
  --fetch \
  --limit 5 \
  --no-write \
  --allow-bs-fallback
```

Optional output:

```bash
--output data/processed/alpaca_greeks_candidates.csv
```

## Greeks policy

| Source | Meaning |
|--------|---------|
| `alpaca_snapshot` | Delta/gamma (minimum) from Alpaca chain snapshot |
| `computed_bs` | BSM fallback; not ground truth |
| `missing` | No usable greeks |

| Status | Meaning |
|--------|---------|
| `AVAILABLE` | Alpaca snapshot greeks used |
| `COMPUTED` | BS fallback used |
| `MISSING` | IV/greeks unavailable and fallback not allowed or incomplete |
| `INVALID_INPUTS` | Missing bid/ask, unknown type, T≤0 without floor, etc. |

**0DTE:** If time to expiry is zero or negative, greeks are **not** computed with T=0 unless `--min-time-to-expiry-days` is explicitly set (documented floor only).

## Boundaries

- No order or position endpoints.
- No MCP transport, paper submission, or live trading.
- No broad universe / full OPRA pulls (fetch is limited to blueprint symbol, expiration window, strike band).
- No Databento fetch.
- No `ReplayContext`, PnL, structure candidates, or trade approval.

**Databento** remains the precision layer for high-fidelity **historical replay**. This layer explores Alpaca-first greeks for live/paper **selection** only.

**Option Alpha spread math** (`spread_math` + PMP table) remains the required expression gate **later**; this packet does not run STRUCT-MATH or approve trades.

## Module

`src/qops/backtest/alpaca_greeks_layer.py`
