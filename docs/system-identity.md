# System identity

A **deterministic, paper-only** options decision system with **required** ML and subagent advisory layers plus a **bounded** probabilistic context layer (Claude overlay and research comparisons). It removes structurally invalid or context-degraded setups before any transport handoff—not by predicting markets, but by enforcing playbook, RR, and PMP constraints.

**Claude proposes** (interpretation, memos, bounded spread alternatives within canonical structures, research filters). **The system decides** (gates, approval, payloads). **Transport executes** (mock offline today; future paper MCP only).

**Constraint Survivability:** AI can generate actions; constraint systems determine which actions are allowed. Automation creates leverage; constraints determine whether that leverage survives scale.

The problem is not getting systems to act. It is getting them to act consistently.

---

## STRUCTURE POLICY

The spread builder may emit:

- `BULL_CALL_SPREAD`
- `BEAR_PUT_SPREAD`
- `BULL_PUT_CREDIT_SPREAD`
- `BEAR_CALL_CREDIT_SPREAD`
- `SKIP`

No parked structures.

All executable structures must remain multi-leg, risk-defined option spreads.

Single-leg long calls / long puts may be analyzed for context, but they are not the canonical execution path.

Credit spreads are allowed only when max loss, collateral requirement, width, premium, and risk/reward are explicitly validated.

Debit spreads are allowed only when debit, max loss, max profit, RR, and PMP/EV thresholds are explicitly validated.

**Underlying price guard:**

- Prefer candidates with underlying price under $100 for early paper-trading expansion.
- Higher-priced underlyings require explicit review because wider markets and larger notional exposure can distort bid/ask, slippage, and position sizing.

**Liquidity guard:**

- Spreads with loose bid/ask must be skipped or downgraded.
- No spread may pass risk approval without explicit bid/ask awareness.

Paper-only execution remains mandatory. Only validated multi-leg spreads that pass deterministic gates may continue to automated paper transport.

---

## ML / SUBAGENT POLICY

ML and subagent review are **required** advisory layers.

They do not own approval.

They may:

- score candidate quality
- identify deteriorating reward/risk
- flag skew, volatility, spread-width, and liquidity concerns
- compare debit vs credit expression
- downgrade candidate confidence
- recommend `SKIP`

They may not:

- approve trades
- override gates
- create execution payloads
- call broker or MCP transport
- mutate thresholds
- bypass risk guard

The deterministic engine remains the decision owner.

**More agents do not mean more authority.** Subagents and ML scorers use the same bounded validation path as every other assistant.
