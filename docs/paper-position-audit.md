# Paper position audit (POSITION-C1)

## Purpose

Read-only **post-fill** check that expected **mleg option legs** appear in the Alpaca **paper account** after MCP-C12A transport and order status audit. No submit, cancel, replace, close, or position mutations.

## Input / output

| Path | Role |
|------|------|
| `data/processed/paper_order_status_audit.csv` | Primary input (default `--input`) |
| `data/processed/paper_transport_results.csv` | Fallback when status audit file is absent |
| `data/processed/paper_payload_candidates.csv` | Leg expectations joined by `payload_id` (internal, not CLI) |
| `data/processed/paper_position_audit.csv` | Output (default `--output`) |

## Row selection

**Status audit input:** rows with `current_status=filled`, non-empty `external_order_id`, empty `failure_reasons`.

**Transport fallback:** rows with `transport_status=PAPER_SUBMITTED` and non-empty `external_order_id`.

Apply `--limit` (default **1**) after filtering.

## Authentication and endpoint

Same paper triplet and canonical URL rules as [alpaca-paper-bridge.md](./alpaca-paper-bridge.md) and [paper-order-status-audit.md](./paper-order-status-audit.md).

## Broker I/O

Single read per run: Alpaca **`get_all_positions`** on the paper trading client. Legs are matched by option `symbol`, `side` (`long` / `short`), and quantity when payload qty is known.

## Position statuses

| Status | Meaning |
|--------|---------|
| `POSITION_CONFIRMED` | Both expected legs present with matching side/qty |
| `POSITION_PARTIAL` | One leg present |
| `POSITION_NOT_FOUND` | Positions fetch OK but neither leg matched |
| `POSITION_AUDIT_ERROR` | Fetch failed or missing expected leg symbols |

## Audit CSV columns

`payload_id`, `approval_id`, `external_order_id`, `symbol`, `structure_type`, `expected_long_leg_symbol`, `expected_short_leg_symbol`, `long_leg_position_found`, `short_leg_position_found`, `long_leg_qty`, `short_leg_qty`, `position_status`, `checked_at`, `failure_reasons`, `provenance`.

## Usage

```bash
PYTHONPATH=src python examples/check_paper_positions.py \
  --input data/processed/paper_order_status_audit.csv \
  --output data/processed/paper_position_audit.csv \
  --limit 1

PYTHONPATH=src python examples/check_paper_positions.py --limit 1 --no-write
```

## Module

`src/qops/execution/paper_position_audit.py` — `run_paper_position_audit` with injectable `get_positions_fn` for tests.
