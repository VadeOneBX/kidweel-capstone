# Notebook alignment: Alpaca bull call spread (NOTEBOOK-ALIGN-C1)

## Purpose

Audit-only alignment between the uploaded Alpaca article notebook and Kidweel’s **paper-live** pipeline (greeks staging → spread candidates → PMP/RR/EV → approval → payload → transport → audits → closeout). Reduce invented complexity by documenting **one canonical shape** and rejecting unsafe notebook patterns.

**Notebook:** [examples/options-bull-call-spread.ipynb](../examples/options-bull-call-spread.ipynb)

**Canonical parameter references:** `src/qops/config/paper_live_params.py` (`NOTEBOOK_BULL_CALL_REFERENCE`, `REPO_PAPER_LIVE_DEFAULTS`).

This packet does **not** submit or close orders, change gates, or add live trading.

---

## Audit table

| Notebook section | Repo equivalent | Keep | Change | Risk |
|------------------|-----------------|------|--------|------|
| Colab Secrets / inline `API_KEY` | `.env` + `ALPACA_PAPER_*` / `ALPACA_API_KEY` split; never commit secrets | Env-based creds; paper vs market-data separation | Document only; no Colab path | Credential leak if copied |
| `TradingClient` + shared URL for data/trade | Paper: `alpaca_paper_bridge`; data: `OptionHistoricalDataClient` | Paper canonical URL guard | Keep split | Live endpoint if merged |
| Trade params (`STRIKE_RANGE`, `BUY_POWER_LIMIT`, `OI_THRESHOLD`, DTE 21–60, IV/delta/vega ranges, roll exits) | `paper_live_params.py` reference vs `REPO_PAPER_LIVE_DEFAULTS`; roll exits **not** in repo | Notebook as **reference**; repo DTE **0–14** default via CLI | Document 21–60 as notebook reference, not mandatory | Confusing DTE if docs imply lock-in |
| `get_options` chain filter (strike band, expiration window) | C4A blueprint `strike_buffer_pct` + DTE window; `--paper-live` in `alpaca_greeks_layer` | Narrow-before-fetch | Align naming in docs (`strike_range_pct` ≈ strike buffer) | Full-chain scan cost |
| Quote / mid from chain snapshot | `alpaca_greeks_layer._extract_quote`; spread gen liquidity | Bid/ask mid for economics | Consolidate mid helper (see below) | Illiquid quotes |
| Inline BSM + `calculate_greeks` | Alpaca snapshot greeks + optional `--allow-bs-fallback` in greeks layer | Prefer vendor greeks; BSM fallback gated | Do not duplicate BSM in execution | Model drift vs vendor |
| `validate_sufficient_OI` / `OI_THRESHOLD=50` | Chain OI in C13F snapshots; spread gen uses quote liquidity not same OI gate | OI in chain exports | Optional future OI floor in staging (policy packet) | Thin markets |
| `check_candidate_option_conditions` (IV/delta/vega/DTE tuple) | Spread pairing + `spread_math` + PMP proxy (`pmp_proxy.py`) + RR/EV gates | Repo uses **policy** PMP table, not notebook IV bands | Do not copy notebook IV/delta bands into gates | Gate bypass |
| `find_options_for_bull_call_spread` pairing | `spread_candidate_generator._pair_bull_call` + fixed width (`DEFAULT_BULL_CALL_WIDTH`) | Long below/near spot, short higher strike, debit math | Document pairing shape match | Width vs notebook dynamic pairing |
| Buying power check (`buying_power_limit`) | Paper approval / payload sizing (not notebook % in repo) | Risk-defined spreads only | Document BP limit as future approval enhancement | Oversize if ignored |
| `MarketOrderRequest` mleg submit | `LimitOrderRequest` mleg; dry-run default; `--submit-paper` opt-in | **Limit only**; deterministic `client_order_id` | Never adopt market mleg | Slippage / uncontrolled fill |
| Inline `submit_order` in notebook | `examples/submit_paper_payload_candidates.py` + audit CSVs | Explicit submit + audits | Keep | No audit trail in notebook |
| `roll_rinse_bull_call_spread` (delta/vega/target % exits) | **Not automated** in repo (policy exits elsewhere) | Concept reference for monitoring | Do not auto-roll in execution | Strategy mutation |
| Per-leg `close_position` on rinse | CLOSE-C1 **single mleg limit** close; quote mid pricing | Two-leg atomic close; no per-leg close | CLOSE-C1B quote mids | Legging risk |
| Notebook close uses short-leg price heuristics | `spread_close_pricing`: `long_mid - short_mid` (bull call) | Quote-based spread mid | No `filled_avg_price` submit | Wrong close price |

---

## Canonical bull-call helper path (repo)

One documented pipeline (no new modules required):

1. **Plan window** — `alpaca_blueprint_adapter` / `--paper-live` DTE (`REPO_PAPER_LIVE_DEFAULTS.dte_min`–`dte_max`, default **0–14**).
2. **Fetch & narrow** — `alpaca_greeks_layer` option chain snapshot; strikes from blueprint buffer (`strike_buffer_pct` / `MAX_STRIKE_DISTANCE_PCT`).
3. **Quote mid & greeks** — Prefer Alpaca snapshot; optional BSM fallback when allowed.
4. **Filter calls & pair** — `spread_candidate_generator` (liquid quotes, width, bull call pairing).
5. **Economics & gates** — `spread_math` → PMP proxy / vendor PMP → RR/EV (unchanged policy).
6. **Approval & payload** — `paper_approval` → `paper_payload_candidate`.
7. **Transport & audits** — explicit paper submit; status/position/closeout CSVs.

Notebook steps map to stages 2–4 plus informal gates; repo adds deterministic policy layers 5–7.

---

## Parameters adopted (documented)

| Parameter | Notebook reference | Repo default / location |
|-----------|-------------------|-------------------------|
| `strike_range_pct` | 0.06 (`STRIKE_RANGE`) | Blueprint `strike_buffer_pct` 0.03; `MAX_STRIKE_DISTANCE_PCT` 0.10 |
| `buy_power_limit_pct` | 0.05 | Documented only (`NOTEBOOK_BULL_CALL_REFERENCE`) |
| `risk_free_rate` | 0.01 | BSM fallback in greeks layer when enabled |
| `oi_threshold` | 50 | Not enforced in spread gen (documented reference) |
| `dte_min` / `dte_max` | 21 / 60 | **0 / 14** paper-live CLI (`REPO_PAPER_LIVE_DEFAULTS`) |
| `target_profit_percentage` | 0.40 | Not auto-exit in repo (monitoring / future packet) |
| `delta_stop_loss` | 0.80 | Not auto-exit in repo |
| `vega_stop_loss` | 0.40 | Not auto-exit in repo |
| `iv_range` | (0.20, 0.50) | Not copied into PMP/RR gates |
| `delta_range` | (0.20, 0.65) | PMP uses short-leg delta **proxy**, not notebook bands |
| `vega_range` | (0.01, 0.12) | Not copied into gates |
| Close spread mid | Implicit in roll logic | `spread_close_pricing` debit: `long_mid - short_mid` |

**DTE:** The notebook’s **21–60 calendar-day** window is a **configurable reference**, not a repo requirement. Paper-live tests may use **0–14** (or any valid `dte_min`–`dte_max`); Kidweel is **not 0DTE-locked** (see `docs/alpaca-blueprint-replay.md`).

---

## Unsafe notebook behaviors (rejected)

| Behavior | Repo stance |
|----------|-------------|
| Market order mleg | Limit orders only; no market close/submit |
| Inline submit without audit | Dry-run default; CSV audits; explicit flags |
| Per-leg `close_position` | Single mleg close with `sell_to_close` / `buy_to_close` legs |
| Colab Secrets / keys in notebook cells | `.env` / env vars; gitignored secrets |
| No deterministic `client_order_id` | `qops-paper-{payload_id}` / `qops-paper-close-{payload_id}` |
| No audit CSV trail | Transport, status, position, closeout CSVs |
| Entry fill as close price | CLOSE-C1B quote mids or explicit `--limit-price` only |

---

## CLOSE-C1B vs notebook “rinse”

- **Notebook:** Monitors short call; may `close_position` each leg; re-opens spread in a loop.
- **Repo:** Read-only quote mids for **both legs** → spread close mid → **one** limit mleg close order; no per-leg close unless a future explicit emergency mode is approved.

See [paper-closeout.md](./paper-closeout.md).

---

## Consolidation opportunities (report only)

| Duplication | Suggestion |
|-------------|------------|
| Bid/ask mid parsing | `alpaca_greeks_layer._extract_quote` vs `spread_close_pricing.leg_mid_from_bid_ask` | Single shared quote-mid helper in one module when a pricing packet touches both |
| BSM / IV | Notebook inline vs greeks layer fallback | Keep BSM only in greeks staging path |
| Strike band | Notebook `STRIKE_RANGE`, blueprint `%`, `constants.MAX_STRIKE_DISTANCE_PCT` | Document mapping in `paper_live_params`; avoid a third band constant |
| OI filter | Notebook threshold vs chain snapshot OI column | If OI gate added, one constant in `paper_live_params` consumed by staging |
| DTE | CLI flags, blueprint adapter, notebook reference | `REPO_PAPER_LIVE_DEFAULTS` + CLI remain source of truth for runs |

Do **not** add parallel abstractions in this packet; reduce CLOSE-C1B scope using this map.

---

## Related docs

- [alpaca-greeks-layer.md](./alpaca-greeks-layer.md) — paper-live fetch, DTE CLI
- [alpaca-blueprint-replay.md](./alpaca-blueprint-replay.md) — configurable DTE, not 0DTE-locked
- [paper-closeout.md](./paper-closeout.md) — limit mleg close + quote mids
