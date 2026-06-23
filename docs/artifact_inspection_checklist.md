# Artifact inspection checklist

Use this checklist when reviewing a morning run before paper submission is considered (submission still requires a dedicated approval packet).

## Per-run artifacts

| Artifact | Typical path |
|----------|----------------|
| Manifest | `data/runs/<run_date>/<run_id>_orb_manifest.json` |
| Context | manifest `context_artifact` |
| Candidates | manifest `candidates_artifact` |
| Risk audit | manifest `risk_audit_artifact` |
| Hydration expressions | `data/processed/<run_id>_alpaca_hydration_expressions.csv` |
| Claude brief | `data/advisory/<run_id>_claude_brief.md` |
| WATCH promotion log | `data/processed/runs/<run_id>/watch_promotion_review.csv` (if operator reviewed) |

## Required checks

- [ ] `run_id` consistent across manifest, expressions CSV, and brief
- [ ] `live_mode_enabled` is `false`
- [ ] `broker_mutation_occurred` is `false`
- [ ] `candidate_loop_status` distribution (hydration pending, watch available, no viable expression, etc.)
- [ ] `hydration_status` distribution
- [ ] `expression_status` distribution (PRIMARY, WATCH, FAILED_EXPRESSION, operator states if present)
- [ ] `dealer_gate_tier` distribution (A–E)
- [ ] `dealer_direction_score_source` / `dealer_direction_score_status` for reverse_vrp rows (`reverse_vrp_iv_rv_wall_skew`, `SOURCE_DERIVED`)
- [ ] Symbols with context but zero expressions (`expression_count` / `no_expression_reason`)
- [ ] WATCH expressions eligible for operator review (`expression_status=WATCH`, tier C or D)
- [ ] No credential-like strings in artifacts (see [claude_code_access_runbook.md](claude_code_access_runbook.md))

## NIO / ETHA focus

When either symbol appears, inspect (candidates + expressions):

- `source_profile`, `current_price`, `call_wall`, `put_wall`, `hedge_wall`
- `one_month_iv`, `one_month_rv`, `iv_rank`, `vrp`
- `structure_bias`, `playbook`
- `gamma_ratio_source`, `chain_fetch_status` (if present on audit row)
- `eligible_expiration_count`, `eligible_strike_count`, `quote_row_count` (if present)
- `expression_count`, `candidate_loop_status`, `no_expression_reason`
- `watch_expression_count` (expressions file aggregate or per-symbol filter)
- `dealer_direction_score`, `dealer_direction_score_source`, `dealer_direction_score_status`

## Safe symbol filter

```bash
grep -R "NIO\|ETHA" data/processed/ docs/audit/ data/advisory/
```

```bash
python - <<'PY'
import pandas as pd
from pathlib import Path
run_id = "2026-06-22-manual-215206"
expr = Path(f"data/processed/{run_id}_alpaca_hydration_expressions.csv")
if expr.is_file():
    df = pd.read_csv(expr)
    print(df[df["symbol"].isin(["NIO", "ETHA"])].to_string())
PY
```

## WATCH promotion

Operator promotion is explicit only (`scripts/review_watch_expression.py`). Successful approve sets `paper_route_status=PAPER_REVIEW_READY` in the review CSV; it does not submit orders.
