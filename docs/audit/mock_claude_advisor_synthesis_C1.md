# Mock workflow stage 3 — claude-advisor synthesis (C1)

**Role:** Bounded synthesis per `docs/claude-advisor-context.md`. Flags only — no approval, sizing, or transport.

## Thesis vs math

- **Squeeze group:** Elevated `gamma_ratio` from scanner suggests dealer positioning interest; a thesis can be interesting and still fail the math.
- **BULL_CALL_SPREAD:** Defined-risk expression when debit, width, RR, and PMP pass deterministic gates — not decided here.

## Advisory flags (mock)

| Symbol cluster | Flag | Rationale |
|----------------|------|-----------|
| POET, NVTS, LUNR | ADVISORY_CAUTION | High gamma_ratio; verify liquidity and width before structure build |
| PATH (repeat dates) | ADVISORY_DOWNGRADE | Repeat appearance — concentration / churn risk in mock portfolio |
| Rows with synthetic strikes | ADVISORY_SKIP | missing_context on chain — mock row only |

## Doctrine strings (packet language)

- Advisory can warn, not act.
- Adding agents does not change the approval path.
- Transport only runs after payload approval.
- The system cannot skip the check.
- Claude can compare arguments. It cannot move the order.

## Handoff

Mock backtest reviewer consumes `docs/backtests/mock_squeeze_bull_call_spread_50_trades_C1.md` — evidence for reconciliation, not for paper submit.
