# Mock workflow stage 2 — squeeze-candidates (C1)

**Role:** Rank and memo squeeze-profile replay candidates. Advisory only — no approval.

## Source

`data/processed/spotgamma_replay_candidates.csv` filtered to `source_profile=squeeze` (44 rows in local file).

## Top candidates (by gamma_ratio, illustrative)

| Rank | Symbol | trade_date | gamma_ratio | candidate_reason (prefix) |
|------|--------|------------|-------------|---------------------------|
| 1 | POET | 2026-04-15 | 4.6916 | squeeze_profile_candidate |
| 2 | NVTS | 2026-04-15 | 3.0486 | squeeze_profile_candidate |
| 3 | LUNR | 2026-04-14 | 2.7036 | squeeze_profile_candidate |
| 4 | CIFR | 2026-04-15 | 2.6190 | squeeze_profile_candidate |
| 5 | LUMN | 2026-04-14 | 2.6753 | squeeze_profile_candidate |
| 6 | HIMS | 2026-04-14 | 2.1619 | squeeze_profile_candidate |
| 7 | AMPX | 2026-04-15 | 2.2694 | squeeze_profile_candidate |
| 8 | HTZ | 2026-04-14 | 1.9497 | squeeze_profile_candidate |

## Structure bias (advisory, not gate output)

- Packet focus: **BULL_CALL_SPREAD** mock backtest from squeeze **source_group** only.
- High gamma_ratio names flagged **ADVISORY_CAUTION** for liquidity / event risk — still requires deterministic spread math and PMP on the main path.

## missing_context

- No Alpaca chain snapshot joined in this workflow.
- Earnings / top_gamma_exp from raw xlsx not re-parsed in this memo.

## Stage output

Eight names above seed the mock 50-trade table (symbol + entry_date from repo); remaining rows use synthetic option fields per backtest artifact labels.
