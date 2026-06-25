# Paper bull call spread C1 runbook (PAPER-BULL-CALL-C1)

**Goal:** Execute (or cleanly reject) a **multi-leg bull call spread** on **Alpaca paper** with advisory and audit evidence. No live trading. No hardcoded tickers—cheap names (e.g. NIO, BB) still must pass spread economics, quotes, PMP/RR, max loss, and transport gates.

**Related:** [evidence_artifacts_guide.md](./evidence_artifacts_guide.md), [connectors_c1_runbook.md](./connectors_c1_runbook.md), [alpaca-paper-bridge.md](./alpaca-paper-bridge.md), [paper-payload-candidates.md](./paper-payload-candidates.md), [paper-order-status-audit.md](./paper-order-status-audit.md).

---

## Acceptance criteria (packet)

| Requirement | Pass condition |
|-------------|----------------|
| Structure | `BULL_CALL_SPREAD` only |
| Mode | Paper (`ALPACA_PAPER_*`, canonical paper URL) |
| Quantity | **2** contracts when guards allow (see sizing below) |
| Underlying | Liquid / cheap candidate preferred—not guaranteed |
| Evidence | Morning brief + risk audit and/or transport audit |
| Reconciliation | `check_paper_order_status.py` after real submit |

A morning run with **zero** `APPROVED_PAPER` rows but a populated risk audit and brief is **valid reject evidence**. A full transport path with **`--submit-paper`** plus status audit satisfies the submit path.

---

## Two paths (do not confuse)

### Path A — Morning loop (candidate / expression guard)

```bash
PYTHONPATH=src python scripts/orb_morning_loop.py --mode manual --base-dir .
PYTHONPATH=src python scripts/operator_status.py --run-id <run_id>
```

- Produces: manifest, `data/processed/risk/<run_id>_risk_audit.csv`, `data/advisory/<run_id>_claude_brief.md`.
- Classifications such as `WATCH_EXPRESSION_AVAILABLE`, `NO_VIABLE_EXPRESSION`, `ALTERNATES_AVAILABLE` are **parked**, not paper-approved.
- **Does not submit.**

Use this for daily advisory accept/reject evidence. Inspect BCS rows:

```bash
python - <<'PY'
import pandas as pd
run_id = "REPLACE_RUN_ID"
df = pd.read_csv(f"data/processed/risk/{run_id}_risk_audit.csv")
bcs = df[df["structure"].astype(str) == "BULL_CALL_SPREAD"]
print(bcs[["symbol","classification","reject_reason","max_loss","rr_actual","pmp"]].to_string(index=False))
PY
```

### Path B — Spread math → approval → payload → transport

Separate explicit packet (after morning review):

```bash
# 1) Math-gated spreads from staged greeks (refresh fetch first if stale)
PYTHONPATH=src python examples/generate_spread_candidates.py \
  --structure BULL_CALL_SPREAD \
  --output data/processed/spread_candidates.csv

# 2) Paper approval (default max risk 600 per candidate)
PYTHONPATH=src python examples/build_paper_approval_candidates.py \
  --input data/processed/spread_candidates.csv \
  --output data/processed/paper_approval_candidates.csv

# 3) Payload shape (mleg limit day)
PYTHONPATH=src python examples/build_paper_payload_candidates.py \
  --input data/processed/paper_approval_candidates.csv \
  --output data/processed/paper_payload_candidates.csv

# 4) Dry-run (default)
PYTHONPATH=src python examples/submit_paper_payload_candidates.py \
  --input data/processed/paper_payload_candidates.csv \
  --output data/processed/paper_transport_results.csv

# 5) Env check (no secrets printed)
PYTHONPATH=src python examples/submit_paper_payload_candidates.py --env-check

# 6) Paper submit (operator opt-in only)
PYTHONPATH=src python examples/submit_paper_payload_candidates.py \
  --input data/processed/paper_payload_candidates.csv \
  --output data/processed/paper_transport_results.csv \
  --submit-paper \
  --limit 1

# 7) Reconcile
PYTHONPATH=src python examples/check_paper_order_status.py \
  --input data/processed/paper_transport_results.csv \
  --output data/processed/paper_order_status_audit.csv
```

Use **run-scoped** filenames (e.g. `paper_bull_c1_*.csv`) when experimenting so default processed files stay unchanged.

---

## Quantity = 2 (sprint target)

`paper_approval.py` sets `suggested_contract_qty=1` when a row is `APPROVED_FOR_PAPER_REVIEW`. For **2** contracts:

1. Filter approval CSV to `APPROVED_FOR_PAPER_REVIEW` + `BULL_CALL_SPREAD`.
2. Confirm `2 * max_loss <= --max-risk` (default **600**).
3. Set `suggested_contract_qty=2` on that row only.
4. Re-run `build_paper_payload_candidates.py` on the filtered CSV.

Payload rules copy qty to `qty`, `long_leg_qty`, and `short_leg_qty` ([paper-payload-candidates.md](./paper-payload-candidates.md)).

---

## WATCH expressions (operator only)

When the risk audit shows `WATCH_EXPRESSION_AVAILABLE` for a BCS expression:

```bash
PYTHONPATH=src python scripts/review_watch_expression.py \
  --run-id <run_id> \
  --expression-id '<expression_id>' \
  --decision approve \
  --reason '<operator reason>' \
  --dry-run
```

`--no-dry-run` appends `watch_promotion_review.csv`; it still **does not** submit. Continue on Path B after promotion if spread rows exist.

---

## Cheap underlyings (NIO / BB)

Not special-cased in code. If scanner + hydration produce no viable expression, expect `NO_VIABLE_EXPRESSION` in the risk audit (valid guard evidence). Prefer symbols with `PRIMARY` BCS expressions and passing spread math on Path B.

---

## Safety

- `touch data/.execution_halt` blocks transport where honored.
- Never use live URL or `ALPACA_LIVE_TRADE`.
- Claude / advisory agents do not run `--submit-paper`.

---

## Packet evidence record

See [audit/paper_bull_call_c1_evidence.md](./audit/paper_bull_call_c1_evidence.md) for the latest recorded dry-run and morning-run outcomes on this workspace.
