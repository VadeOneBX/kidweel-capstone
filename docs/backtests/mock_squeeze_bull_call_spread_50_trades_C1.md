# Mock squeeze bull call spread backtest (C1)

**Evidence class:** mock / advisory-only. Not live trading results. Strikes, debits, and PnL are **synthetic** except symbol and entry_date sourced from `data/processed/spotgamma_replay_candidates.csv` (squeeze profile) where noted.

Claude can compare arguments. It cannot move the order.

## Trade table

| trade_id | symbol | source_group | structure_type | entry_date | expiration | dte | long_strike | short_strike | debit | max_profit | max_loss | rr_actual | pmp | min_rr_required | expected_value | spread_delta | advisory_status | gate_status | exit_reason | realized_pnl | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SQC1-001 | PATH | SQUEEZE | BULL_CALL_SPREAD | 2026-04-14 | 2026-06-03 | 50 | 189 | 199 | 2.64 | 7.36 | 2.64 | 2.788 | 0.64 | 0.25 | 3.76 | 0.44 | ADVISORY_SKIP | SKIP | SKIP | 0.0 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-002 | LUMN | SQUEEZE | BULL_CALL_SPREAD | 2026-04-14 | 2026-05-13 | 29 | 368 | 373 | 0.93 | 4.07 | 0.93 | 4.376 | 0.83 | 0.25 | 3.22 | 0.53 | ADVISORY_CAUTION | FAIL | EXPIRATION_MAX | 4.07 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-003 | HTZ | SQUEEZE | BULL_CALL_SPREAD | 2026-04-14 | 2026-05-26 | 42 | 371 | 376 | 0.46 | 4.54 | 0.46 | 9.87 | 0.46 | 0.25 | 1.84 | 0.26 | ADVISORY_CAUTION | WATCH | STOP | -0.46 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-004 | ASTS | SQUEEZE | BULL_CALL_SPREAD | 2026-04-14 | 2026-06-08 | 55 | 124 | 134 | 0.99 | 9.01 | 0.99 | 9.101 | 0.79 | 0.25 | 6.91 | 0.49 | ADVISORY_OK | FAIL | EXPIRATION_LOSS | -0.99 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-005 | HIMS | SQUEEZE | BULL_CALL_SPREAD | 2026-04-14 | 2026-05-31 | 47 | 176 | 181 | 0.51 | 4.49 | 0.51 | 8.804 | 0.51 | 0.25 | 2.04 | 0.41 | ADVISORY_CAUTION | FAIL | STOP | -0.51 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-006 | LUNR | SQUEEZE | BULL_CALL_SPREAD | 2026-04-14 | 2026-05-12 | 28 | 357 | 362 | 2.32 | 2.68 | 2.32 | 1.155 | 0.72 | 0.25 | 1.28 | 0.52 | ADVISORY_SKIP | SKIP | SKIP | 0.0 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-007 | ONDS | SQUEEZE | BULL_CALL_SPREAD | 2026-04-15 | 2026-05-15 | 30 | 244 | 254 | 1.69 | 8.31 | 1.69 | 4.917 | 0.79 | 0.25 | 6.21 | 0.39 | ADVISORY_DOWNGRADE | FAIL | EXPIRATION_LOSS | -1.69 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-008 | NVTS | SQUEEZE | BULL_CALL_SPREAD | 2026-04-15 | 2026-06-04 | 50 | 209 | 214 | 1.84 | 3.16 | 1.84 | 1.717 | 0.84 | 0.25 | 2.36 | 0.54 | ADVISORY_SKIP | SKIP | SKIP | 0.0 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-009 | CIFR | SQUEEZE | BULL_CALL_SPREAD | 2026-04-15 | 2026-05-30 | 45 | 259 | 264 | 2.34 | 2.66 | 2.34 | 1.137 | 0.54 | 0.25 | 0.36 | 0.34 | ADVISORY_OK | WATCH | EXPIRATION_LOSS | -2.34 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-010 | AMPX | SQUEEZE | BULL_CALL_SPREAD | 2026-04-15 | 2026-05-20 | 35 | 84 | 94 | 2.09 | 7.91 | 2.09 | 3.785 | 0.79 | 0.25 | 5.81 | 0.39 | ADVISORY_DOWNGRADE | FAIL | EXPIRATION_LOSS | -2.09 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-011 | POET | SQUEEZE | BULL_CALL_SPREAD | 2026-04-15 | 2026-05-14 | 29 | 303 | 308 | 1.28 | 3.72 | 1.28 | 2.906 | 0.58 | 0.25 | 1.62 | 0.38 | ADVISORY_CAUTION | WATCH | EXPIRATION_MAX | 3.72 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-012 | PATH | SQUEEZE | BULL_CALL_SPREAD | 2026-04-15 | 2026-05-13 | 28 | 132 | 137 | 1.07 | 3.93 | 1.07 | 3.673 | 0.47 | 0.25 | 1.28 | 0.47 | ADVISORY_CAUTION | FAIL | TIME_EXIT | 0.97 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-013 | DVN | SQUEEZE | BULL_CALL_SPREAD | 2026-04-15 | 2026-06-06 | 52 | 276 | 286 | 1.51 | 8.49 | 1.51 | 5.623 | 0.71 | 0.25 | 5.59 | 0.31 | ADVISORY_OK | FAIL | STOP | -1.51 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-014 | CDE | SQUEEZE | BULL_CALL_SPREAD | 2026-04-15 | 2026-05-13 | 28 | 117 | 122 | 0.92 | 4.08 | 0.92 | 4.435 | 0.72 | 0.25 | 2.68 | 0.42 | ADVISORY_SKIP | SKIP | SKIP | 0.0 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-015 | HIMS | SQUEEZE | BULL_CALL_SPREAD | 2026-04-15 | 2026-05-07 | 22 | 216 | 221 | 0.91 | 4.09 | 0.91 | 4.495 | 0.51 | 0.25 | 1.64 | 0.31 | ADVISORY_OK | FAIL | STOP | -0.91 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-016 | SMR | SQUEEZE | BULL_CALL_SPREAD | 2026-04-15 | 2026-05-21 | 36 | 275 | 285 | 0.5 | 9.5 | 0.5 | 19.0 | 0.7 | 0.25 | 6.5 | 0.3 | ADVISORY_DOWNGRADE | WATCH | TP_80 | 7.6 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-017 | BTDR | SQUEEZE | BULL_CALL_SPREAD | 2026-04-15 | 2026-06-06 | 52 | 46 | 51 | 1.21 | 3.79 | 1.21 | 3.132 | 0.81 | 0.25 | 2.84 | 0.41 | ADVISORY_CAUTION | PASS | STOP | -1.21 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-018 | LUNR | SQUEEZE | BULL_CALL_SPREAD | 2026-04-15 | 2026-05-09 | 24 | 143 | 148 | 2.68 | 2.32 | 2.68 | 0.866 | 0.58 | 0.25 | 0.22 | 0.48 | ADVISORY_DOWNGRADE | WATCH | EXPIRATION_MAX | 2.32 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-019 | FSLY | SQUEEZE | BULL_CALL_SPREAD | 2026-04-15 | 2026-06-06 | 52 | 131 | 141 | 2.56 | 7.44 | 2.56 | 2.906 | 0.46 | 0.25 | 2.04 | 0.26 | ADVISORY_CAUTION | WATCH | STOP | -2.56 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-020 | POET | SQUEEZE | BULL_CALL_SPREAD | 2026-04-16 | 2026-05-23 | 37 | 141 | 146 | 1.66 | 3.34 | 1.66 | 2.012 | 0.56 | 0.25 | 1.14 | 0.36 | ADVISORY_SKIP | SKIP | SKIP | 0.0 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-021 | NUAI | SQUEEZE | BULL_CALL_SPREAD | 2026-04-16 | 2026-06-03 | 48 | 247 | 252 | 0.72 | 4.28 | 0.72 | 5.944 | 0.82 | 0.25 | 3.38 | 0.52 | ADVISORY_OK | WATCH | TIME_EXIT | 1.14 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-022 | PATH | SQUEEZE | BULL_CALL_SPREAD | 2026-04-16 | 2026-05-20 | 34 | 43 | 53 | 1.18 | 8.82 | 1.18 | 7.475 | 0.78 | 0.25 | 6.62 | 0.48 | ADVISORY_DOWNGRADE | WATCH | EXPIRATION_MAX | 8.82 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-023 | ASTS | SQUEEZE | BULL_CALL_SPREAD | 2026-04-16 | 2026-05-16 | 30 | 74 | 79 | 1.99 | 3.01 | 1.99 | 1.513 | 0.69 | 0.25 | 1.46 | 0.49 | ADVISORY_OK | PASS | EXPIRATION_LOSS | -1.99 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-024 | USAR | SQUEEZE | BULL_CALL_SPREAD | 2026-04-16 | 2026-05-16 | 30 | 129 | 134 | 0.54 | 4.46 | 0.54 | 8.259 | 0.84 | 0.25 | 3.66 | 0.44 | ADVISORY_SKIP | SKIP | SKIP | 0.0 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-025 | HIMS | SQUEEZE | BULL_CALL_SPREAD | 2026-04-16 | 2026-06-07 | 52 | 366 | 376 | 0.41 | 9.59 | 0.41 | 23.39 | 0.81 | 0.25 | 7.69 | 0.41 | ADVISORY_CAUTION | PASS | STOP | -0.41 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-026 | UUUU | SQUEEZE | BULL_CALL_SPREAD | 2026-04-16 | 2026-05-11 | 25 | 74 | 79 | 0.49 | 4.51 | 0.49 | 9.204 | 0.69 | 0.25 | 2.96 | 0.39 | ADVISORY_DOWNGRADE | PASS | EXPIRATION_LOSS | -0.49 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-027 | QUBT | SQUEEZE | BULL_CALL_SPREAD | 2026-04-16 | 2026-05-27 | 41 | 35 | 40 | 2.6 | 2.4 | 2.6 | 0.923 | 0.7 | 0.25 | 0.9 | 0.3 | ADVISORY_DOWNGRADE | WATCH | TP_80 | 1.92 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-028 | SOUN | SQUEEZE | BULL_CALL_SPREAD | 2026-04-16 | 2026-05-30 | 44 | 373 | 383 | 0.98 | 9.02 | 0.98 | 9.204 | 0.48 | 0.25 | 3.82 | 0.38 | ADVISORY_SKIP | SKIP | SKIP | 0.0 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-029 | CIFR | SQUEEZE | BULL_CALL_SPREAD | 2026-04-16 | 2026-05-27 | 41 | 390 | 395 | 1.65 | 3.35 | 1.65 | 2.03 | 0.65 | 0.25 | 1.6 | 0.35 | ADVISORY_CAUTION | PASS | TP_80 | 2.68 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-030 | SMR | SQUEEZE | BULL_CALL_SPREAD | 2026-04-16 | 2026-05-29 | 43 | 242 | 247 | 2.17 | 2.83 | 2.17 | 1.304 | 0.77 | 0.25 | 1.68 | 0.47 | ADVISORY_CAUTION | PASS | TIME_EXIT | 0.41 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-031 | ONDS | SQUEEZE | BULL_CALL_SPREAD | 2026-04-16 | 2026-05-08 | 22 | 216 | 226 | 1.41 | 8.59 | 1.41 | 6.092 | 0.51 | 0.25 | 3.69 | 0.31 | ADVISORY_OK | FAIL | STOP | -1.41 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-032 | RGTI | SQUEEZE | BULL_CALL_SPREAD | 2026-04-16 | 2026-05-20 | 34 | 348 | 353 | 1.73 | 3.27 | 1.73 | 1.89 | 0.63 | 0.25 | 1.42 | 0.33 | ADVISORY_DOWNGRADE | FAIL | EXPIRATION_MAX | 3.27 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-033 | IREN | SQUEEZE | BULL_CALL_SPREAD | 2026-04-16 | 2026-05-09 | 23 | 37 | 42 | 2.12 | 2.88 | 2.12 | 1.358 | 0.72 | 0.25 | 1.48 | 0.42 | ADVISORY_SKIP | SKIP | SKIP | 0.0 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-034 | MP | SQUEEZE | BULL_CALL_SPREAD | 2026-04-16 | 2026-06-06 | 51 | 265 | 275 | 1.9 | 8.1 | 1.9 | 4.263 | 0.6 | 0.25 | 4.1 | 0.3 | ADVISORY_SKIP | SKIP | SKIP | 0.0 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-035 | RKLB | SQUEEZE | BULL_CALL_SPREAD | 2026-04-16 | 2026-05-17 | 31 | 135 | 140 | 2.1 | 2.9 | 2.1 | 1.381 | 0.5 | 0.25 | 0.4 | 0.5 | ADVISORY_CAUTION | WATCH | TP_80 | 2.32 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-036 | PYPL | SQUEEZE | BULL_CALL_SPREAD | 2026-05-28 | 2026-07-20 | 53 | 132 | 137 | 1.57 | 3.43 | 1.57 | 2.185 | 0.47 | 0.25 | 0.78 | 0.37 | ADVISORY_OK | FAIL | TIME_EXIT | 0.71 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-037 | SNAP | SQUEEZE | BULL_CALL_SPREAD | 2026-05-28 | 2026-06-23 | 26 | 195 | 205 | 2.2 | 7.8 | 2.2 | 3.545 | 0.7 | 0.25 | 4.8 | 0.5 | ADVISORY_CAUTION | WATCH | TP_80 | 6.24 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-038 | OKLO | SQUEEZE | BULL_CALL_SPREAD | 2026-05-28 | 2026-07-20 | 53 | 82 | 87 | 2.07 | 2.93 | 2.07 | 1.415 | 0.77 | 0.25 | 1.78 | 0.27 | ADVISORY_DOWNGRADE | PASS | TIME_EXIT | 0.47 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-039 | EOSE | SQUEEZE | BULL_CALL_SPREAD | 2026-05-28 | 2026-06-18 | 21 | 70 | 75 | 1.95 | 3.05 | 1.95 | 1.564 | 0.65 | 0.25 | 1.3 | 0.45 | ADVISORY_DOWNGRADE | PASS | TP_80 | 2.44 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-040 | RIOT | SQUEEZE | BULL_CALL_SPREAD | 2026-05-28 | 2026-06-28 | 31 | 210 | 220 | 0.35 | 9.65 | 0.35 | 27.571 | 0.45 | 0.25 | 4.15 | 0.45 | ADVISORY_DOWNGRADE | PASS | TP_80 | 7.72 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-041 | QUBT | SQUEEZE | BULL_CALL_SPREAD | 2026-05-28 | 2026-06-24 | 27 | 196 | 201 | 2.21 | 2.79 | 2.21 | 1.262 | 0.71 | 0.25 | 1.34 | 0.41 | ADVISORY_CAUTION | FAIL | STOP | -2.21 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-042 | QBTS | SQUEEZE | BULL_CALL_SPREAD | 2026-05-28 | 2026-06-28 | 31 | 310 | 315 | 1.85 | 3.15 | 1.85 | 1.703 | 0.65 | 0.25 | 1.4 | 0.35 | ADVISORY_CAUTION | PASS | TP_80 | 2.52 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-043 | RGTI | SQUEEZE | BULL_CALL_SPREAD | 2026-05-28 | 2026-07-02 | 35 | 249 | 259 | 2.24 | 7.76 | 2.24 | 3.464 | 0.84 | 0.25 | 6.16 | 0.44 | ADVISORY_SKIP | SKIP | SKIP | 0.0 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-044 | TE | SQUEEZE | BULL_CALL_SPREAD | 2026-05-28 | 2026-06-22 | 25 | 234 | 239 | 1.09 | 3.91 | 1.09 | 3.587 | 0.69 | 0.25 | 2.36 | 0.49 | ADVISORY_OK | PASS | EXPIRATION_LOSS | -1.09 | mock_backtest_not_live;option_fields:repo_context_symbol_date |
| SQC1-045 | PATH | SQUEEZE | BULL_CALL_SPREAD | 2026-04-14 | 2026-06-04 | 51 | 350 | 355 | 2.75 | 2.25 | 2.75 | 0.818 | 0.65 | 0.25 | 0.5 | 0.45 | ADVISORY_DOWNGRADE | PASS | TP_80 | 1.8 | synthetic_row;mock_backtest_not_live;option_fields:synthetic_mock |
| SQC1-046 | PATH | SQUEEZE | BULL_CALL_SPREAD | 2026-04-14 | 2026-06-03 | 50 | 204 | 214 | 0.79 | 9.21 | 0.79 | 11.658 | 0.79 | 0.25 | 7.11 | 0.39 | ADVISORY_DOWNGRADE | FAIL | EXPIRATION_LOSS | -0.79 | synthetic_row;mock_backtest_not_live;option_fields:synthetic_mock |
| SQC1-047 | PATH | SQUEEZE | BULL_CALL_SPREAD | 2026-04-14 | 2026-05-05 | 21 | 135 | 140 | 1.6 | 3.4 | 1.6 | 2.125 | 0.5 | 0.25 | 0.9 | 0.4 | ADVISORY_OK | WATCH | TP_80 | 2.72 | synthetic_row;mock_backtest_not_live;option_fields:synthetic_mock |
| SQC1-048 | PATH | SQUEEZE | BULL_CALL_SPREAD | 2026-04-14 | 2026-05-31 | 47 | 346 | 351 | 1.71 | 3.29 | 1.71 | 1.924 | 0.61 | 0.25 | 1.34 | 0.41 | ADVISORY_CAUTION | PASS | STOP | -1.71 | synthetic_row;mock_backtest_not_live;option_fields:synthetic_mock |
| SQC1-049 | PATH | SQUEEZE | BULL_CALL_SPREAD | 2026-04-14 | 2026-05-20 | 36 | 315 | 325 | 0.4 | 9.6 | 0.4 | 24.0 | 0.7 | 0.25 | 6.6 | 0.4 | ADVISORY_OK | WATCH | TP_80 | 7.68 | synthetic_row;mock_backtest_not_live;option_fields:synthetic_mock |
| SQC1-050 | PATH | SQUEEZE | BULL_CALL_SPREAD | 2026-04-14 | 2026-05-19 | 35 | 274 | 279 | 1.49 | 3.51 | 1.49 | 2.356 | 0.69 | 0.25 | 1.96 | 0.29 | ADVISORY_CAUTION | PASS | EXPIRATION_LOSS | -1.49 | synthetic_row;mock_backtest_not_live;option_fields:synthetic_mock |

## Summary metrics

- trade_count: 50
- pass_count: 14
- watch_count: 13
- fail_count: 13
- skip_count: 10
- win_rate: 0.525 (synthetic_mock — excludes SKIP rows from denominator)
- net_pnl: 45.68 (synthetic_mock)
- profit_factor: 2.766 (synthetic_mock)
- avg_rr_actual: 5.402
- avg_pmp: 0.661 (synthetic_mock — not production PMP gate output)
- avg_expected_value: 2.934 (synthetic_mock)
- stop_rate: 0.2
- time_exit_rate: 0.1
- max_drawdown_estimate: 8.08 (synthetic_approx on row order)

## Source files (read-only)

- `data/processed/spotgamma_replay_candidates.csv` — 44 squeeze-profile candidate rows available locally
- `data/spotgamma/raw/*/squeeze.xlsx` — raw scanner exports (not parsed in this artifact)

## missing_context

- Historical option chain / fills not joined — all strikes, debits, and realized_pnl are mock.
- Equities: current-session SG only unless replay row date present in CSV.
