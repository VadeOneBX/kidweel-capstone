# Spread candidate generation (STRUCT-C2)

## Purpose

Connect **Alpaca greeks/quote staging** to **canonical vertical spreads** and run every candidate through **Option Alpha spread math** (`evaluate_spread_math` / PMP table).

This is **candidate generation only**:

- No execution payloads
- No MCP or paper transport
- No `ReplayContext` or PnL
- No Databento
- No strategy optimization

Claude / ML / subagents are **downstream advisory** layers only; they cannot override spread math.

## Inputs

`data/processed/alpaca_greeks_candidates.csv` from ALPACA-GREEKS-C1 (`--fetch` required for contract rows).

Optional column: `probability_of_profit` (never fabricated).

If the CSV is missing or empty, generation returns **zero candidates** and documents that fetched quote rows are required.

## PMP rule

**PMP is never fabricated.** If `probability_of_profit` is absent from staging input:

- Spread economics still compute (`max_profit`, `max_loss`, `reward_risk`, `break_even`, `capital_at_risk`).
- `pmp_status` is **MISSING**; `math_status` is **INCOMPLETE** or **WATCH**.
- **`candidate_pass` is false** even when core debit/credit math is valid.

A future packet may add an explicit, tested PMP proxy; Claude/subagent advisory cannot supply PMP.

## Greeks confidence

`computed_bs` staging rows may pair into spreads for quote-driven math; leg columns `long_greeks_source` / `long_greeks_confidence` (and short leg) record **lower confidence** than vendor snapshot greeks. Missing greeks rows with valid bid/ask may still pair; they do not imply greek-dependent confidence.

## Quote pairing

| Structure | Long leg | Short leg | Premium |
|-----------|----------|-----------|---------|
| `BULL_CALL_SPREAD` | Lower call | Higher call | Long ask − short bid (debit) |
| `BEAR_PUT_SPREAD` | Higher put | Lower put | Long ask − short bid (debit) |
| `BULL_PUT_CREDIT_SPREAD` | Lower put | Higher put | Short bid − long ask (credit) |
| `BEAR_CALL_CREDIT_SPREAD` | Higher call | Lower call | Short bid − long ask (credit) |

Filters: bid/ask > 0, ask ≥ bid, positive width and debit/credit, same expiration and option type, bid/ask spread % ≤ `--max-bid-ask-spread-pct` (default 0.25).

## Math gate

Every candidate calls `evaluate_spread_math`. When PMP is **missing**, probability/EV status is **INCOMPLETE/WATCH** and **`candidate_pass` is false** even if core economics pass.

`build_structure_candidate` runs only when quote width matches the builder’s default scaffold width (5.0) so economics stay consistent.

## CLI

```bash
PYTHONPATH=src python examples/generate_spread_candidates.py \
  --input data/processed/alpaca_greeks_candidates.csv \
  --no-write \
  --limit 25
```

```bash
--structure ALL          # default
--structure BULL_CALL_SPREAD   # repeatable filter
--max-bid-ask-spread-pct 0.25
--output data/processed/spread_candidates.csv
```

## Module

`src/qops/strategy/spread_candidate_generator.py`
