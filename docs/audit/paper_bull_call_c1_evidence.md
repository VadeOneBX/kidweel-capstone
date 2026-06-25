# Paper bull call C1 — evidence record

**Packet:** PAPER-BULL-CALL-C1  
**Recorded:** 2026-06-23 (workspace local artifacts; `data/` is gitignored)

---

## 1. Morning run — deterministic guard (reject path)

| Field | Value |
|-------|--------|
| `run_id` | `2026-06-23-manual-091340` |
| Manifest status | `ADVISORY_COMPLETE` |
| `live_mode_enabled` | `false` |
| `broker_mutation_occurred` | `false` |
| Risk audit | `data/processed/risk/2026-06-23-manual-091340_risk_audit.csv` |
| Advisory brief | `data/advisory/2026-06-23-manual-091340_claude_brief.md` |

**Roll-up:** 21 candidates; **0** approved for paper; 14 `WATCH_EXPRESSION_AVAILABLE`, 6 `NO_VIABLE_EXPRESSION`, 1 `ALTERNATES_AVAILABLE`.

**Bull call spread rows (10):** All parked (e.g. dealer-tier selection), not `APPROVED_PAPER`. Example:

| symbol | classification | reject_reason (abridged) |
|--------|----------------|---------------------------|
| IBIT | ALTERNATES_AVAILABLE | Primary expression selected; alternate retained |
| SOFI, USAR, … | WATCH_EXPRESSION_AVAILABLE | Expression not selected under dealer-weighted tier |

**Cheap tickers:** NIO — `NO_VIABLE_EXPRESSION` (`expression_search_exhausted:no_viable_expression`). ETHA — same. No BB rows in this run.

**Packet verdict:** Valid **clean guard reject** evidence with advisory brief attached.

---

## 2. Transport path — dry-run (submit path prep)

| Step | Artifact | Outcome |
|------|----------|---------|
| BCS spread generation | `data/processed/paper_bull_c1_spread_candidates.csv` | 50 rows; **1** `candidate_pass` |
| Paper approval | `data/processed/paper_bull_c1_approval.csv` | **1** `APPROVED_FOR_PAPER_REVIEW` (NKE BCS) |
| Qty 2 override | `data/processed/paper_bull_c1_approval_ready.csv` | `suggested_contract_qty=2`, `max_loss=0.14` per spread |
| Payload | `data/processed/paper_bull_c1_payload.csv` | **1** `PAPER_PAYLOAD_READY`, `BULL_CALL_SPREAD` |
| Transport dry-run | `data/processed/paper_bull_c1_transport_results.csv` | `PAPER_DRY_RUN_READY`, `dry_run_no_broker_call` |

**Env check:** `credential_status: READY`, `endpoint_ok: True` (paper triplet present locally; values not recorded here).

**Operator note:** The approved NKE legs in this chain use expiration **2026-06-18** from stale greeks staging. Before a real `--submit-paper`, regenerate spreads from **current** hydration/greeks for a forward expiration (e.g. IBIT `PRIMARY` BCS on the latest run) and repeat Path B in [paper_bull_call_c1_runbook.md](../paper_bull_call_c1_runbook.md).

---

## 3. Real paper submit (operator step)

Not executed in the automated doc pass (requires explicit operator confirmation). When ready:

```bash
PYTHONPATH=src python examples/submit_paper_payload_candidates.py \
  --input data/processed/paper_bull_c1_payload.csv \
  --output data/processed/paper_bull_c1_transport_results.csv \
  --submit-paper \
  --limit 1

PYTHONPATH=src python examples/check_paper_order_status.py \
  --input data/processed/paper_bull_c1_transport_results.csv \
  --output data/processed/paper_bull_c1_order_status.csv
```

Append broker `transport_status` / `current_status` to this file after submit.

---

## 4. Advisory cross-reference

Morning brief excerpt: approved (paper-only review) **0**; parked **21**; guardrails show no live path. Full text: `data/advisory/2026-06-23-manual-091340_claude_brief.md`.
