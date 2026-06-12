# Paper payload candidates (PAYLOAD-C1)

## Purpose

Deterministic **paper order payload** preparation from rows already at **`APPROVED_FOR_PAPER_REVIEW`**. This layer does **not** submit orders, call MCP, call Alpaca, or mutate accounts.

Status **`PAPER_PAYLOAD_READY`** means the row is shaped for a future transport packet only—not execution by itself.

## Input / output

- Input: `data/processed/paper_approval_candidates.csv`
- Output: `data/processed/paper_payload_candidates.csv`

## Rules

Only input rows with **`approval_status=APPROVED_FOR_PAPER_REVIEW`** and successful payload validation can reach **`PAPER_PAYLOAD_READY`**.

- `qty`, `long_leg_qty`, and `short_leg_qty` equal **`suggested_contract_qty`** (never overridden or sized above it).
- `order_class = mleg`, `order_type = limit`, `time_in_force = day`.
- **`limit_price`** is **`net_debit_or_credit`** from approval:
  - Debit spreads: positive net debit paid to open.
  - Credit spreads: positive net credit received to open (same numeric field; leg sides encode sell-short / buy-hedge semantics).

## Leg sides

| structure_type | long_leg | short_leg |
|----------------|----------|-----------|
| BULL_CALL_SPREAD | buy call | sell call |
| BEAR_PUT_SPREAD | buy put | sell put |
| BULL_PUT_CREDIT_SPREAD | buy long put (hedge) | sell short put |
| BEAR_CALL_CREDIT_SPREAD | buy long call (hedge) | sell short call |

## CLI

```bash
PYTHONPATH=src python examples/build_paper_payload_candidates.py \
  --input data/processed/paper_approval_candidates.csv \
  --no-write \
  --limit 50
```

## Module

`src/qops/execution/paper_payload_candidate.py`
