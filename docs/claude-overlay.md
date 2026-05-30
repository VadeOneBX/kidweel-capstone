# Claude overlay (C11B-lite)

## Authority

**Claude proposes; the system decides.** Transport executes separately and only for repo-approved payloads.

Claude may not approve, size, execute, route, or override gates.

## Role

Claude acts as an **overlay governor** on prepared context: it may emit a typed memo (surface, market, term, caution/downgrade flags) and **bounded spread alternatives** only inside [canonical allowed structures](./system-identity.md#structure-policy). It is **not** a decision engine for this repository.

ML and subagent review are required advisory layers alongside overlay; none of them own approval.

## Interpretation (allowed)

Claude may interpret, among other signals:

- put skew increased
- downside risk dominates
- condor asymmetry
- reward/risk deteriorating
- spread liquidity concern
- credit risk not worth premium
- debit risk/reward deteriorating

Claude may propose bounded spread alternatives only within:

- `BULL_CALL_SPREAD`
- `BEAR_PUT_SPREAD`
- `BULL_PUT_CREDIT_SPREAD`
- `BEAR_CALL_CREDIT_SPREAD`
- `SKIP`

No parked structures. Single-leg long calls or long puts may inform context but are not the canonical execution path.

## This packet (overlay wiring)

- **Memo and advisory**: assessments are logged, segmented, and shown in backtest evidence.
- **No approval rights**: overlay does not change risk approval, RR, or PMP, and does not override gates.
- **No execution rights**: no hooks into execution payloads or MCP transport.

Claude may annotate, downgrade confidence, and recommend stricter posture or `SKIP`.  
Claude may not approve, size, execute, or call transport.

## Future implementation

Code packets may lag this canonical policy. When implementation catches up, bounded structure suggestions remain proposals until deterministic gates approve a handoff—same as every other advisory input.
