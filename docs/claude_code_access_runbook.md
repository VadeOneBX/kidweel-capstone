# Claude Code repo access runbook

Bounded **read-only** visibility for artifact inspection and code trace. This is enablement for review, not execution authority.

## Allowed

- Read repository source under `src/`, `scripts/`, `tests/`, and `docs/`
- Inspect generated artifacts under `data/processed/`, `docs/audit/`, and `data/advisory/`
- Summarize candidate and expression evidence from CSV/JSON manifests
- Identify missing fields, trace function paths, suggest patches, and review tests

## Forbidden

1. Never open or print `.env`
2. Never print credential-like values (API keys, secrets, tokens)
3. Never add `.env` to git
4. Never call paper submit scripts (`run_paper_payload_transport`, `--submit-paper`, etc.)
5. Never call MCP submit tools for orders
6. Never set `ALPACA_LIVE_TRADE` or enable live trading
7. Do not authorize broker mutation or act as operator approval without explicit human action
8. Limit artifact reads to `data/processed/`, `docs/audit/`, `data/advisory/`, and run manifests under `data/runs/`

## Pre-share grep (no key leakage)

Before pasting artifact excerpts externally:

```bash
grep -R -E 'AKIA|sk-|api_key|secret|password|ALPACA_.*KEY' data/processed/ docs/audit/ data/advisory/ data/runs/ || true
```

## Safe inspection commands

```bash
grep -R "NIO\|ETHA" data/processed/ docs/audit/ data/advisory/
```

```bash
PYTHONPATH=src python scripts/operator_status.py --run-id 2026-06-22-manual-215206
```

```bash
python - <<'PY'
import pandas as pd
p = "data/processed/2026-06-22-manual-215206_alpaca_hydration_expressions.csv"
df = pd.read_csv(p)
cols = [
    "symbol", "source_profile", "structure", "expression_status",
    "dealer_gate_tier", "dealer_direction_score", "dealer_direction_score_source",
    "dealer_direction_score_status",
]
present = [c for c in cols if c in df.columns]
print(df[df["symbol"].isin(["NIO", "ETHA"])][present].head(20).to_string())
PY
```

WATCH operator review (dry-run default; does **not** submit):

```bash
PYTHONPATH=src python scripts/review_watch_expression.py \
  --run-id 2026-06-22-manual-215206 \
  --expression-id '<expression_id>' \
  --decision approve \
  --reason '<operator reason>' \
  --dry-run
```

## Paper safety

- Paper transport remains repo-gated and opt-in under separate approval packets
- Claude Code does not own approval, sizing, or transport
