# Alpaca paper transport bridge (MCP-C12A)

## Purpose

Transport **`PAPER_PAYLOAD_READY`** payload candidates to **Alpaca paper** only when **`--submit-paper`** is explicitly passed. Default behavior is **dry-run** (no broker I/O).

No approval, strategy, sizing, or MCP judgment in this layer.

## Input / output

- Input: `data/processed/paper_payload_candidates.csv`
- Output: `data/processed/paper_transport_results.csv`

## Authentication modes (`--auth-mode`)

| Mode | `--env-check` | `--submit-paper` |
|------|---------------|------------------|
| **`env_triplet`** (default) | Requires `ALPACA_PAPER_*` triplet + canonical paper URL | **Supported** (only submit path today) |
| **`profile_cli`** | Read-only `alpaca profile show --quiet` + `alpaca account get --quiet` | **Not implemented** — fails closed with `PROFILE_CLI_SUBMIT_NOT_IMPLEMENTED` |

`profile_cli` is for confirming local Alpaca CLI paper profile readiness when `ALPACA_PAPER_*` is not set. It does not submit orders or call order endpoints.

Alpaca CLI stores profiles **outside the repo** (typically `~/.config/alpaca/profiles/`). Optional environment:

- **`ALPACA_CONFIG_DIR`** — alternate config directory (passed through to CLI subprocess; never read or printed by this repo).
- **`ALPACA_PROFILE`** — active profile name (passed through to CLI subprocess).
- **`ALPACA_LIVE_TRADE=true`** (or `1` / `yes`) — **forbidden** for this repo (`LIVE_ENV_FORBIDDEN`).

Paper is the Alpaca CLI default; live keys require explicit `--live` at login (never used here). If paper secrets are missing locally, regenerate paper API credentials in Alpaca and store them only in local profile/config — not in git.

Profile CLI rules:

- Always pass **`--quiet`** on Alpaca CLI invocations from automation (repo env-check does).
- **Never** pass **`--secret`** or **`--live`**.
- Alpaca CLI **exit code 2** = authentication failure — fix credentials; do not retry blindly.
- Submit still requires explicit **`--submit-paper`** and a supported auth path (`env_triplet` only for now).

```bash
PYTHONPATH=src python examples/submit_paper_payload_candidates.py \
  --auth-mode profile_cli \
  --env-check
```

## Environment (paper transport only)

Prefer **`ALPACA_PAPER_*`** (not market-data `ALPACA_API_KEY` / greeks credentials):

| Variable | Required |
|----------|----------|
| `ALPACA_PAPER_API_KEY` | Yes (`env_triplet` submit + env-check) |
| `ALPACA_PAPER_SECRET_KEY` | Yes |
| `ALPACA_PAPER_BASE_URL` | Yes — must be exactly `https://paper-api.alpaca.markets` |

Optional alias triplet (same rules):

- `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`, `APCA_API_BASE_URL`

**Fail closed:** live endpoint `https://api.alpaca.markets`, missing URL, or non-canonical paper URL → no submit.

## Transport statuses

- `PAPER_DRY_RUN_READY` — validated ready row, no broker call
- `PAPER_SUBMITTED` — normalized accept from paper API
- `PAPER_REJECTED` — broker declined (normalized `accepted=False`)
- `PAPER_TRANSPORT_ERROR` — submit/normalize failure
- `PAPER_SKIPPED` — reserved; non-ready rows are filtered out, not transported

## Alpaca mleg mapping (adapter)

Repo payload fields map to `alpaca-py` `LimitOrderRequest` with `order_class=mleg`:

| Payload field | Alpaca field |
|---------------|--------------|
| `symbol` | parent `symbol` (underlying) |
| `qty` | parent `qty` |
| `order_type=limit` | `OrderType.LIMIT` |
| `time_in_force=day` | `TimeInForce.DAY` |
| `limit_price` | net `limit_price` (debit: positive; credit structures: negated magnitude) |
| `long_leg_*` / `short_leg_*` | `OptionLegRequest` legs with `side` + `ratio_qty` |
| Debit spreads | parent `side=BUY` |
| Credit spreads | parent `side=SELL` |

Payload candidate schema is unchanged; adapter lives in `build_alpaca_mleg_order_request`.

Broker responses are narrowed to the five-key dict consumed by `normalize_mcp_response`.

## CLI

Dry-run (default):

```bash
PYTHONPATH=src python examples/submit_paper_payload_candidates.py \
  --input data/processed/paper_payload_candidates.csv \
  --no-write \
  --limit 5
```

Env check:

```bash
PYTHONPATH=src python examples/submit_paper_payload_candidates.py --env-check
```

Submit (explicit, default `--limit 1`):

```bash
PYTHONPATH=src python examples/submit_paper_payload_candidates.py \
  --submit-paper \
  --limit 1
```

## Credential separation

- **Market data / greeks** (`ALPACA_API_KEY`, `ALPACA_SECRET_KEY`): read-only chain and greeks staging only.
- **Paper transport** (`ALPACA_PAPER_*`): required for `--submit-paper`. Market-data keys must **not** be silently reused for order transport.

## Automation safety

- Default CLI path is **dry-run** (no broker I/O). `--submit-paper` is opt-in.
- Submit mode defaults to **`--limit 1`** unless explicitly raised.
- Each submit sets **`client_order_id`** to `qops-paper-{payload_id}` so retries after ambiguous failures do not duplicate orders blindly.
- Single submit attempt per payload (no retry loop). Fix credentials or endpoint before re-running.
- CLI prints one JSON object per transport row on stdout for parse-safe automation (no secret values).
- `--env-check` exits non-zero when paper credentials or canonical endpoint are missing/invalid.

## Alpaca / Paper Trading Anti-Patterns

- **NEVER** switch to live trading without explicit user intent. Alpaca profile login defaults to paper trading; do not pass `--live` unless the user specifically asks for it.
- **NEVER** pass `--secret` as a CLI flag. It leaks into shell history. Use `alpaca profile login` interactively or set `ALPACA_SECRET_KEY` / `ALPACA_PAPER_SECRET_KEY` as an environment variable.
- **NEVER** omit `--quiet` in automation or agent workflows when using **Alpaca CLI** commands. Without it, stderr may include hints and warnings that break parsing.
- **NEVER** ignore exit code **2** from Alpaca CLI. Treat it as authentication failure. Do not retry; fix credentials first.
- **NEVER** hardcode API keys in scripts or committed files. Use environment variables, local `.env` files (gitignored), or profile-based auth.
- **NEVER** submit live orders without confirming the user's explicit intent. Use `--dry-run` to preview first when there is any ambiguity.
- **NEVER** submit orders without a deterministic client/order id in automation. Without it, retries after ambiguous failures such as timeouts or network errors risk placing duplicate orders.

## Module

`src/qops/execution/alpaca_paper_bridge.py`
