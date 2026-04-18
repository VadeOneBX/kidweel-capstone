# C13E — MCP chain enrichment (ChatGPT payload)

## Purpose

After C13D exports a ChatGPT bridge JSON with a `chain_context` stub, this packet fills that field using **delayed** options-chain snapshots from **local** CSV files (the same shape as MCP-fed Alpaca chain data). This is research-only context for ChatGPT synthesis, not execution or approval.

## Data flow

SpotGamma → C13D `chatgpt_payload_*.json` → **C13E enrichment** (this packet) → `chatgpt_payload_enriched_*.json` → ChatGPT.

## Input

1. **Payload JSON** — `data/spotgamma/processed/chatgpt_payload_YYYYMMDD.json` (or `chatgpt_payload_multi_session.json`) produced by C13D.

2. **Chain snapshots** — One CSV per symbol under a chosen directory, named exactly `{symbol}.csv` where `{symbol}` matches the payload row (case-sensitive). Required columns:

   - `expiration`
   - `strike`
   - `option_type` (`call` / `put`, case-insensitive)
   - `open_interest`

## Output

- Single trade date → `chatgpt_payload_enriched_YYYYMMDD.json`
- Multiple trade dates in one file → `chatgpt_payload_enriched_multi_session.json`

Written to `--output-dir` (default `data/spotgamma/processed`).

## `chain_context` fields

Populated to match the C13D stub, using the same summarization as C13C (`qops.context.mcp_chain_summary.summarize_delayed_chain`):

- `nearest_expiration`
- `highest_oi_strike`
- `total_call_oi`
- `total_put_oi`
- `dominant_side`
- `concentration_near_spot` (uses candidate `price` as spot for the ±5% band on the nearest expiry)
- `movement_bias`

If no `{symbol}.csv` exists for a row, `chain_context` is left unchanged and the row is counted as skipped.

## CLI

```bash
PYTHONPATH=src python -m qops.bridge.run_mcp_enrichment \
  --payload data/spotgamma/processed/chatgpt_payload_20260416.json \
  --chain-dir /path/to/mcp_chain_snapshots \
  --output-dir data/spotgamma/processed
```

Compact summary lines:

- `payload_count`
- `symbols_enriched` (rows with a snapshot applied)
- `symbols_skipped` (rows without a matching file)
- `output_path`

## Verification

```bash
PYTHONPATH=src python -m compileall src/qops/bridge
PYTHONPATH=src python -c "from qops.bridge import mcp_enrichment, run_mcp_enrichment"
```

Use a test `--chain-dir` with minimal valid CSVs per symbol to confirm JSON round-trip and enrichment.
