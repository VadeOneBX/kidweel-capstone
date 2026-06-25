# Threshold sweep (THRESH-C1)

## Purpose

Non-destructive **threshold sensitivity harness** on existing staged spread candidates. It answers how many rows remain **eligible_for_trade_review** when decision variables tighten—not how to tune the strategy for better backtests.

This is **analysis only**:

- No changes to canonical gates, PMP table, spread math, approval, or payload logic
- No paper submit, close, live trading, or Alpaca calls
- Missing values are counted, not invented

Paper **approved** counts come only from `paper_approval_candidates.csv`. Sweep survivors are labeled **eligible_for_trade_review**, not “tradeable” or “approved” unless the approval file says so.

## Run

```bash
PYTHONPATH=src python examples/run_threshold_sweep.py \
  --input data/processed/spread_candidates.csv \
  --no-write
```

Optional:

- `--input-approvals` — `data/processed/paper_approval_candidates.csv`
- `--input-greeks` — leg bid/ask and `spread_delta` / advisory profile join
- `--output` / `--summary-output`
- `--limit`

## Scenarios

1. **Baseline** — core economics + existing `candidate_pass`
2. **RR floor** — `reward_risk >=` 1.00 … 3.00
3. **EV floor** — `expected_value >=` 0, 0.05, 0.10, 0.25
4. **Bid/ask** — max leg quote width % `<=` 0.50, 0.35, 0.25, 0.15 (requires bid/ask)
5. **Combined** — e.g. EV ≥ 0 and RR ≥ 2.0 and bid/ask ≤ 0.25; EV ≥ 0 and RR ≥ `min_rr_required` and bid/ask ≤ 0.25

Splits reported per scenario: **structure type** and **advisory group** (`SQUEEZE_CANDIDATES`, `VOLATILITY_RISK_PREMIUM`, `REVERSE_RISK_PREMIUM`, `UNKNOWN`).

## Module

[`src/qops/analysis/threshold_sweep.py`](../src/qops/analysis/threshold_sweep.py)

## Natural-language questions

| Question | Where |
|----------|--------|
| “What if we raise the gate so all candidates must be 2:1 reward/risk?” | Scenario `rr_gte_2_00` → `pass_count` |
| “What if EV >= 0 and bid/ask spread is under 0.50?” | `ev_gte_0_and_bid_ask_spread_pct_lte_0_50` |
| “How many pass and are eligible for trade review?” | `pass_count` / `pass_rate` per scenario |
| “Which squeeze candidates pass 2:1 RR and rank best by spread delta?” | Filter `advisory_group == SQUEEZE_CANDIDATES`; `top_10_survivors` sorted by RR, PMP, `spread_delta` |

## Related

- Canonical evidence refresh: [canonical-backtest-refresh.md](./canonical-backtest-refresh.md)
- Spread generation: [spread-candidate-generation.md](./spread-candidate-generation.md)
