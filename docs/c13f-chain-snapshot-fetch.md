# C13F — Delayed options chain snapshot fetch

## Purpose

Packet **C13F** fetches **delayed** option-chain data from Alpaca for tickers that appear in a C13D ChatGPT payload, and writes **canonical local CSVs** for downstream **C13E** enrichment. It does not place orders, size trades, or approve execution.

## Authority split

- **SpotGamma** — which ticker deserves attention (upstream of C13D).
- **Alpaca** — which option contracts exist for that underlying (this packet).
- **ChatGPT** — structure and narrative context (separate bridge steps).

This script does **not** infer movement bias, enrich `chain_context`, or call MCP tools.

## Prerequisites

- Alpaca **Market Data** credentials in the environment (same pattern as other `alpaca-py` usage). Use **delayed / options** data only; follow [Alpaca Market Data API](https://docs.alpaca.markets/docs/about-market-data-api) and your subscription tier.
- **Alpaca MCP Server v2** is the source of truth for MCP/tool behavior in other packets; this CLI uses the **Python** `OptionHistoricalDataClient`, not MCP, for chain snapshots.

## Input

A JSON file exported from C13D — same list shape as `export_chatgpt_payloads` in `src/qops/bridge/export.py`. Rows must include at least:

- `symbol`
- `trade_date` (`YYYY-MM-DD`)
- `price` (spot reference for ATM; first row per unique `(trade_date, symbol)` wins)

## Strike window (ATM)

After the API returns the chain, the exporter **drops strikes outside ±10 rungs of at-the-money** per expiration. ATM is the listed strike closest to the payload `price`. This yields up to **21 strikes per expiry** (10 below, ATM, 10 above). Override with `--strikes-each-side N` (default `10`).

## Output layout

For each unique `(trade_date, symbol)` pair:

```text
{output_root}/{trade_date}/{SYMBOL}.csv
```

Default `output_root`: `data/options/chain_snapshots`.

### Required CSV columns


| Column          | Description                        |
| --------------- | ---------------------------------- |
| `expiration`    | Contract expiration (`YYYY-MM-DD`) |
| `strike`        | Strike price                       |
| `option_type`   | `call` or `put`                    |
| `open_interest` | Open interest (integer)            |


These match what `qops.context.mcp_chain_summary.summarize_delayed_chain` expects in C13E.

## Usage

From the repo root, with `PYTHONPATH=src` (or after `pip install -e .`):

```bash
PYTHONPATH=src python -m qops.bridge.run_chain_snapshot_fetch \
  --input-json path/to/chatgpt_payload_YYYYMMDD.json \
  --output-root data/options/chain_snapshots \
  --strikes-each-side 10
```

The process prints a compact summary: `requested`, `fetched`, `skipped`, and `output_root`.

## Behavior notes

- **Skip gracefully** when the Alpaca API returns no contracts, or when the request fails (e.g. auth, rate limits, network). Those symbols are listed in `skipped_symbols`.
- **Fail** on malformed tabular data that cannot be normalized to the required columns, or on filesystem write errors.
- The client uses **raw** API responses (`raw_data=True`) so contract symbols and `openInterest` align with the HTTP JSON.

## C13E linkage

Point C13E `--chain-dir` at the same **root** used here (e.g. `data/options/chain_snapshots`). Enrichment resolves paths as `{chain-dir}/{trade_date}/{SYMBOL}.csv` per payload row.

## Modules


| File                          | Role                                                                                  |
| ----------------------------- | ------------------------------------------------------------------------------------- |
| `chain_snapshot_models.py`    | Summary dataclass and column constants                                                |
| `chain_snapshot_export.py`    | Payload read, OCC parsing, normalization, Alpaca fetch, ±ATM strike filter, CSV write |
| `run_chain_snapshot_fetch.py` | CLI entrypoint                                                                        |


