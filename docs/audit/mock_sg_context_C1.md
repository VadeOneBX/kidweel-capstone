# Mock workflow stage 1 — sg-context-reader (C1)

**Role:** Advisory reader only. No MCP, no broker, no code changes.

## Inputs read (repo-local)

| Path | Observation |
|------|-------------|
| `data/spotgamma/raw/2026-06-12/squeeze.xlsx` | Present (raw scanner export) |
| `data/spotgamma/raw/2026-06-08/squeeze.xlsx` | Present |
| `data/processed/spotgamma_replay_candidates.csv` | 176 candidate rows; 44 `source_profile=squeeze` |
| `docs/spotgamma-replay-corpus.md` | Documents squeeze profile and non-derived fields |

## SPY context attachment

- Replay CSV includes `squeeze_profile_candidate+spy_context` on sample rows (e.g. PATH, LUMN on 2026-04-14).
- SPY history / session `SPY.xlsx` files exist under `data/spotgamma/raw/*/`.

## Normalized fields available (from docs + CSV headers)

- Symbol, trade_date, gamma_ratio (when present), candidate_reason, source_profile.
- **missing_context:** `regime_label`, `confidence`, `vrp_z` not derived for squeeze rows per corpus doc; not invented here.

## Caveats

- Equities are tied to export session dates in CSV; not a live chain.
- Do not infer SG wall trend for single-name equities beyond supplied scanner fields.

## Stage output

Squeeze scanner exports and normalized replay candidates are **available locally** for advisory memo and mock backtest labeling. Option-level history for backtest rows remains **missing_context** unless a future chain-join packet runs.
