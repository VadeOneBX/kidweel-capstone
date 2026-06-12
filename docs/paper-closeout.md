# Paper mleg closeout (CLOSE-C1 / CLOSE-C1B)

## Purpose

**Controlled** close of a **verified** Alpaca **paper** multileg spread after fill and leg confirmation. Default is **dry-run** (no broker I/O). Real close requires explicit **`--close-paper`**.

Not live trading. Not new opening trades. No changes to approval, payload, spread math, or PMP.

## Inputs / output

| Path | Role |
|------|------|
| `data/processed/paper_order_status_audit.csv` | Filled orders (`current_status=filled`) |
| `data/processed/paper_payload_candidates.csv` | Original legs and structure by `payload_id` |
| `data/processed/paper_position_audit.csv` | Optional context (live positions still re-checked) |
| `data/processed/paper_closeout_results.csv` | Closeout results |

## Preconditions

1. Status audit row: `current_status=filled`, `external_order_id` present, empty `failure_reasons`.
2. Matching payload candidate for `payload_id`.
3. Live paper **`get_all_positions`**: both expected option legs present (`POSITION_CONFIRMED`).

## Close order shape

- `order_class=mleg`, `type=limit`, `time_in_force=day`
- No parent equity `symbol` (option legs only)
- Long leg: **sell** + `sell_to_close`
- Short leg: **buy** + `buy_to_close`
- `client_order_id`: `qops-paper-close-{payload_id}` (deterministic); retries use `-a{N}` suffix when prior closeout rows exist for the same `payload_id` (see `paper_closeout_results.csv`) or `--close-attempt N`.

## Pricing (CLOSE-C1B)

**Quote-based close pricing is implemented** via `src/qops/execution/spread_close_pricing.py`.

- **Market data** credentials (`ALPACA_API_KEY` / `ALPACA_SECRET_KEY`) fetch **latest option quotes** for both legs (read-only; not paper transport keys).
- Leg mid: `(bid + ask) / 2` when both sides are present.
- Spread close mid:
  - Debit structures (`BULL_CALL_SPREAD`, `BEAR_PUT_SPREAD`): `long_mid - short_mid`
  - Credit structures (`BULL_PUT_CREDIT_SPREAD`, `BEAR_CALL_CREDIT_SPREAD`): `short_mid - long_mid`
- **Suggested close limit**: spread mid rounded to **$0.01** (nearest cent).
- **`close_price_source=quote_mid`**, **`close_price_status=AVAILABLE`** when quotes succeed.
- **Entry fill is never used** for submit pricing.
- If quotes are missing: **`close_price_status=MISSING_QUOTES`**; **`--close-paper` is rejected** unless **`--limit-price`** is provided (explicit override).
- **`--price-source quote_mid`** (default). **`--limit-price`** overrides quotes for dry-run and submit.

**Notebook contrast:** The Alpaca bull call notebook uses per-leg `close_position` and roll/rinse heuristics on the short call. Kidweel uses a **single limit mleg** close and **both-leg quote mids** ([notebook-alignment.md](./notebook-alignment.md)). Entry fill is never the submit close price.

## Close statuses

| Status | Meaning |
|--------|---------|
| `PAPER_CLOSE_DRY_RUN_READY` | Verified; close request buildable; no submit |
| `PAPER_CLOSE_SUBMITTED` | Close accepted by paper API |
| `PAPER_CLOSE_REJECTED` | Broker declined close |
| `PAPER_CLOSE_SKIPPED` | Missing payload, not filled, etc. |
| `PAPER_CLOSE_ERROR` | Position/leg/credential/limit failure |

## Usage

Dry-run request review (no submit):

```bash
PYTHONPATH=src python examples/close_paper_position.py \
  --payload-id 0eb54452ad35bb44 \
  --print-request-json \
  --no-write
```

Paper close with quote mid (when `AVAILABLE`):

```bash
PYTHONPATH=src python examples/close_paper_position.py \
  --payload-id 0eb54452ad35bb44 \
  --close-paper \
  --limit 1
```

Explicit limit override:

```bash
PYTHONPATH=src python examples/close_paper_position.py \
  --payload-id 0eb54452ad35bb44 \
  --close-paper \
  --limit-price 0.09
```

## Endpoint

Paper **submit** uses canonical paper URL and `ALPACA_PAPER_*`. Live trading endpoint rejected; fail closed.

## Modules

- `src/qops/execution/paper_closeout.py`
- `src/qops/execution/spread_close_pricing.py`
