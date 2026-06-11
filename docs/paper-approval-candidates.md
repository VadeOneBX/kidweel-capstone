# Paper approval candidates (APPROVAL-C1)

## Purpose

Deterministic **paper review** handoff from spread candidates that already cleared STRUCT-C2 + PMP-C1 gates. This layer does **not** submit orders, call MCP, or build broker payloads.

Status **`APPROVED_FOR_PAPER_REVIEW`** means the row is eligible for a future payload/transport packet only—not live or paper execution by itself.

## Input / output

- Input: `data/processed/spread_candidates.csv`
- Output: `data/processed/paper_approval_candidates.csv`

## Rules

Only rows with **`candidate_pass=True`** and successful re-validation (PMP present, spread math gate, EV **PASS**, probability **PASS**, valid max loss, structure type, leg symbols) can reach **`APPROVED_FOR_PAPER_REVIEW`**.

- No fabricated sizing: `suggested_contract_qty=1` only when approved and `max_loss <= --max-risk` (default **600**).
- `risk_unit = max_loss`.
- If `max_loss > max_risk`, row is **REJECTED** (`max_loss_exceeds_max_risk`).
- Missing required fields → **INCOMPLETE**.

## CLI

```bash
PYTHONPATH=src python examples/build_paper_approval_candidates.py \
  --input data/processed/spread_candidates.csv \
  --max-risk 600 \
  --no-write \
  --limit 50
```

## Module

`src/qops/risk/paper_approval.py`
