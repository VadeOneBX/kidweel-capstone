# Paper order status audit (MCP-C12A-POST1)

## Purpose

Read-only **post-submit** status check for orders already sent to **Alpaca paper** via MCP-C12A transport. This packet does **not** submit, cancel, replace, or modify positions.

## Input / output

| Path | Role |
|------|------|
| `data/processed/paper_transport_results.csv` | Input (default `--input`) |
| `data/processed/paper_order_status_audit.csv` | Output audit (default `--output`) |

## Row selection

1. Load transport results CSV.
2. Keep rows where `transport_status == PAPER_SUBMITTED` and `external_order_id` is non-empty.
3. Apply `--limit` (default **1**) after filtering.

## Authentication and endpoint

Same **paper triplet** and canonical URL rules as [alpaca-paper-bridge.md](./alpaca-paper-bridge.md):

- `ALPACA_PAPER_API_KEY`, `ALPACA_PAPER_SECRET_KEY`, `ALPACA_PAPER_BASE_URL`
- Base URL must be exactly `https://paper-api.alpaca.markets` when `--require-paper-endpoint` is on (default).

Repo-root `.env` is loaded via `python-dotenv` (`override=False`) when resolving credentials.

## Broker I/O

Single read per selected row: Alpaca **`get_order_by_id`** on the paper trading client. No order mutations.

## Audit CSV columns

| Column | Description |
|--------|-------------|
| `payload_id` | From transport results |
| `approval_id` | From transport results |
| `external_order_id` | Alpaca order UUID |
| `broker_mode` | From transport (expected `paper`) |
| `previous_status` | `status` at submit time from transport results |
| `current_status` | Live broker order status |
| `filled_qty` | Broker filled quantity |
| `filled_avg_price` | Broker average fill price |
| `submitted_at` | From transport results |
| `checked_at` | UTC timestamp of this audit run |
| `status_message` | Short audit message (e.g. `order_status:…`) |
| `failure_reasons` | Non-empty when the status fetch failed |

## Usage

```bash
PYTHONPATH=src python examples/check_paper_order_status.py \
  --input data/processed/paper_transport_results.csv \
  --output data/processed/paper_order_status_audit.csv \
  --limit 1

PYTHONPATH=src python examples/check_paper_order_status.py --limit 1 --no-write
```

## Module

Logic lives in `src/qops/execution/paper_order_status.py` (`run_paper_order_status_audit`, injectable `get_order_fn` for tests).
