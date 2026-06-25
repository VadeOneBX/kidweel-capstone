# SpotGamma advisory model

How **SpotGamma-oriented context** feeds advisory flags only—not payloads, gates, or transport.

## Canonical inputs (morning path)

| Input | Location |
|-------|----------|
| Normalized / feature context | manifest `context_artifact` (from ingestion + `qops.context`) |
| Walls, gamma, skew in rows | Context CSV columns and `notes` KV (see ingest docs) |
| Chain / OI enrichment | manifest `expressions_artifact`, optional `scripts/alpaca_fetch.py` JSON |
| Risk outcomes | `data/processed/risk/<run_id>_risk_audit.csv` |

There is **no** required repo file named `sg-context.md`. If the coordinator attaches a memo, reference that path in idea `source` fields.

## Forbidden re-derivation

Do not recompute `regime_label`, `confidence`, or `gamma_ratio` in advisory skills. Missing fields → `missing_context` and stop.

## Related

- [spotgamma-to-replay.md](./spotgamma-to-replay.md) (ingestion; context only)
- [docs/skills/](./skills/) (post-ORB idea templates)
- [system-identity.md](./system-identity.md)
