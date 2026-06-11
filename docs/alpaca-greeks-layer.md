# Alpaca greeks layer (ALPACA-GREEKS-C1)

## Purpose

Alpaca-first greeks staging for **paper-trade candidate selection** (not historical replay precision).

Alpaca’s **0DTE backtesting example** is the **implementation blueprint** (chain snapshot → narrow → enrich). **Kidweel is not locked to 0DTE**; DTE windows come from the C4A blueprint plan and remain **configurable** (e.g. **0–14**). Shorter DTE triggers stricter liquidity, Greek, and timing checks later in the stack.

For each narrowed SG-BT-C4A blueprint row:

1. Prefer **Alpaca option chain snapshot greeks** when present.
2. Fall back to **Black–Scholes / BSM** greeks only when `--allow-bs-fallback` is set and IV (or an explicit `--fallback-volatility-proxy`) is available.
3. Record `greeks_source`, `greeks_status`, and `greeks_confidence` on every contract row.

## Upstream

- Input: `data/processed/alpaca_blueprint_replay_plan.csv`, or rebuild via C4A (`--rebuild-if-missing`).
- SpotGamma → C3 availability → C4A blueprint strike/DTE window.

## Read-only Alpaca market data setup

**Market-data credentials** (this layer) are separate from **paper-trading / order** credentials used elsewhere. The greeks layer uses read-only option chain snapshots only; it does not submit orders, call MCP, or use paper transport.

### Required environment variables

Use **one** complete pair (values never logged or printed):

| Primary | Alternative (Alpaca SDK convention) |
|---------|-------------------------------------|
| `ALPACA_API_KEY` | `APCA_API_KEY_ID` |
| `ALPACA_SECRET_KEY` | `APCA_API_SECRET_KEY` |

Copy `.env.example` to `.env`, fill in keys locally, or `export` in your shell. **Do not commit `.env`** (ignored via `.gitignore`).

```bash
cp .env.example .env
# edit .env locally — never commit
```

### CLI

Dry-run (default — no network, no credentials required):

```bash
PYTHONPATH=src python examples/alpaca_greeks_candidate_stage.py \
  --rebuild-if-missing \
  --no-write \
  --limit 10
```

Credential check only (loads `.env` when `python-dotenv` is installed):

```bash
PYTHONPATH=src python examples/alpaca_greeks_candidate_stage.py --env-check
```

Read-only fetch (`--fetch` required; fails closed if `credential_status=MISSING`):

```bash
PYTHONPATH=src python examples/alpaca_greeks_candidate_stage.py \
  --rebuild-if-missing \
  --fetch \
  --limit 5 \
  --no-write \
  --allow-bs-fallback
```

### Downstream CSV

When fetch succeeds, rows may be written to:

`data/processed/alpaca_greeks_candidates.csv`

(structure candidate generation in STRUCT-C2 consumes this file.)

Optional output path: `--output data/processed/alpaca_greeks_candidates.csv`

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

**Near-expiry greek math (not a 0DTE trading mandate):** If time to expiry is zero or negative, BSM greeks are **not** computed with T=0 unless `--min-time-to-expiry-days` is explicitly set (documented floor only). This guards fragile same-day math; it does not require trading 0DTE structures.

## Boundaries

- No order or position endpoints.
- No MCP transport, paper submission, or live trading.
- No broad universe / full OPRA pulls (fetch is limited to blueprint symbol, expiration window, strike band).
- No Databento fetch.
- No `ReplayContext`, PnL, structure candidates, or trade approval.

**Databento** is a **precision fallback** for high-fidelity **historical replay**, not the default path. This layer explores Alpaca-first greeks for live/paper **selection** only.

**Option Alpha spread math** (`spread_math` + PMP table) remains the required expression gate **later**; this packet does not run STRUCT-MATH or approve trades.

## Module

`src/qops/backtest/alpaca_greeks_layer.py`
