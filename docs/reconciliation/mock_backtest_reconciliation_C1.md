# Mock backtest reconciliation (C1)

**Role:** Reconciliation reviewer — read artifacts only; no source edits.

## Checks

| Check | Result |
|-------|--------|
| candidate_count | 44 squeeze rows in local replay CSV; 8 highlighted in squeeze memo |
| trade_row_count | 50 |
| rows_with_missing_context | 50 (option chain / fills not joined — all rows note `mock_backtest_not_live`) |
| rows_with_synthetic_data | 50 (strikes, debits, PnL synthetic; symbol/date partially from repo) |
| rows_with_invalid_rr | 0 (rr_actual computed from synthetic debit/width; FAIL gates where rr < min_rr_required) |
| rows_with_invalid_pmp | 0 (numeric 0–1 range; labeled synthetic_mock in summary) |
| rows_with_missing_exit_reason | 0 |
| rows_with_non_bull_call_spread | 0 |
| rows_with_forbidden_authority_language | 0 in table cells (doctrine strings only in narrative sections) |
| mcp_calls_detected | 0 |
| broker_calls_detected | 0 |
| source_files_changed | `.gitignore` only (privacy fix); `src/`, `tests/`, `data/` untouched |

## Artifact cross-check

- `docs/audit/mock_sg_context_C1.md` — sources cited match local paths.
- `docs/audit/mock_squeeze_candidates_C1.md` — symbols align with CSV sample.
- `docs/backtests/mock_squeeze_bull_call_spread_50_trades_C1.md` — 50 data rows + summary.
- `docs/audit/mock_claude_advisor_synthesis_C1.md` — advisory-only language.

## Summary metrics (from backtest artifact)

- pass / watch / fail / skip: 14 / 13 / 13 / 10
- net_pnl: 45.68 (synthetic_mock)
- profit_factor: synthetic_mock (see backtest summary)
- win_rate: see backtest summary (synthetic_mock)

## Final status

RECON_PASS_WITH_NOTES

Notes: All PnL and option fields are mock; repo provides symbol/session context only. Do not treat as live results.
