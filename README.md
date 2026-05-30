# KIDWEEL

## What breaks first?

Built from trading.  
Applied everywhere.

A deterministic, paper-only decision system for testing how automated systems remain consistent as authority scales.

- Context becomes structured decisions
- Claude may propose; it cannot approve
- Validation gates decide what continues
- MCP transports approved paper payloads only
- Every outcome should be traceable

Automation creates leverage. Constraints determine whether that leverage survives scale.

---

## What this is

- A complete decision pipeline: context → playbook → structure → validation → payload → paper transport → response → audit
- SpotGamma-oriented ingestion and environment classification within fixed playbooks
- Deterministic gates (playbook policy, RR, PMP, paper execution gate, MCP paper gate)
- Iterative backtest scaffolding (PnL, profit factor, Sharpe, drawdown / stop-rate, playbook segmentation, validation status)
- A **bounded** Claude layer for context interpretation and overlay commentary (not approval or execution)
- Offline **mock** MCP bridge (C11A) plus a narrow transport contract (C10A) for a future real paper MCP bridge
- Constraint Survivability framing: automation creates leverage; constraints determine whether that leverage survives scale

## What this is not

- **Not** a live trading bot
- **Not** autonomous execution or broker-side judgment
- **Not** an AI agent with broker authority, position management, or cancel/replace automation
- **Not** unrestricted order submission

The problem is not getting systems to act. It is getting them to act **consistently** within enforceable constraints.

---

## System loop

```
Context → playbook → structure → validation → payload → paper transport → response → audit
```

SpotGamma and related context feed screening and playbook selection. Structure and risk modules produce approved handoffs only when gates pass. Transport (mock today; Alpaca MCP paper bridge in a future packet) carries **approved** payloads only. Audit records gate outcomes and normalized responses.

---

## Current status

| Area | Status |
|------|--------|
| Deterministic core (playbooks, RR/PMP, structure) | In repo |
| Backtest evidence & Claude research comparisons | In repo |
| Paper execution payload + gates | In repo |
| MCP contract (C10A) | Documented + typed models |
| Mock MCP bridge (C11A) | Offline deterministic path in `src/qops/execution/` |
| Real Alpaca MCP paper client | **Not** implemented — future explicit packet |
| Live trading | **Out of scope** |

---

## Structure and advisory policy

Canonical structure and ML/subagent rules live in [docs/system-identity.md](./docs/system-identity.md).

**Structure:** The spread builder may emit `BULL_CALL_SPREAD`, `BEAR_PUT_SPREAD`, `BULL_PUT_CREDIT_SPREAD`, `BEAR_CALL_CREDIT_SPREAD`, or `SKIP`. No parked structures. Executable paths are multi-leg, risk-defined spreads only (debit and credit when explicitly validated). Single-leg long calls or puts are for context, not canonical execution.

**ML / subagents:** Required advisory layers—they score, flag, compare expressions, downgrade confidence, and may recommend `SKIP`. They do not approve, override gates, mutate thresholds, or call transport. The deterministic engine remains the decision owner.

Paper-only execution remains mandatory.

---

## Claude boundary

Claude may interpret context (skew, liquidity, deteriorating reward/risk, debit vs credit posture) and propose **bounded** spread alternatives only within the canonical structure set above.

Claude **cannot** approve trades, size positions, execute orders, bypass validation, or call broker transport.

Claude proposes; the system decides.

---

## Paper / MCP transport boundary

- **MCP and broker APIs are transport only.** The repo owns approval. Transport carries approved payloads.
- **C10A** (`integrations/alpaca_mcp/transport_contract.md`) defines the narrow request/response contract.
- **C11A** provides an **offline** mock bridge: gate → mock transport → normalize → audit (no network).
- A **future packet** may add a real **paper** Alpaca MCP bridge. Broker-shaped responses must be adapted into the narrow response dict **before** `normalize_mcp_response`.
- Mock transport must not be confused with production MCP I/O.

Transport executes; it does not decide.

---

## Backtest evidence

The backtest layer produces comparative evidence: trade counts, profit factor, Sharpe, drawdown-related metrics, stop-rate, playbook segmentation, and validation status (`eligible_for_paper`, research-mode exceptions). Claude context and overlay paths add **research-only** counterfactuals—they do not change production approval or execution gates.

Example (limited sample, illustrative): see [docs/findings-c13-claude-context.md](./docs/findings-c13-claude-context.md).

---

## Constraint Survivability

As automation scales, systems need **enforceable constraints**. The future is not unconstrained autonomous systems; it is autonomous systems operating within constraints that survive scale.

- AI can generate actions; constraint systems determine which actions are allowed.
- Automation creates leverage; constraints determine whether that leverage survives scale.

See [docs/system-identity.md](./docs/system-identity.md) for the concise identity statement.

---

## Why this matters beyond trading

Modern teams build workflows around Snowflake/Cortex, MCP-connected tools, GPT/Claude reasoning layers, and Cursor-assisted development. **This repo does not integrate those products in production**—there is no Snowflake, Cortex, or GPT integration here.

The **architecture is transferable**: the same pattern applies wherever agents can act—data pipelines, marketing automation, internal ops. The more systems can act, the more important it becomes to define **when** they are allowed to act. This repository is a smaller, stricter demonstration of that pattern.

---

## Subagent / swarm pattern

Multiple agents and ML review assist development and candidate analysis; **authority remains bounded**. ML/subagent review is **required** as an advisory layer, not optional.

**Subagents may propose:** candidate ideas, bounded structure alternatives (canonical spreads only), caution notes, environment summaries, test priorities, confidence downgrades, `SKIP` recommendations.

**Subagents may not:** approve trades, execute orders, bypass gates, mutate playbooks, change thresholds, create execution payloads, or call broker transport.

**Swarm-safe routing:**

1. Agent proposes  
2. Deterministic validator checks  
3. Risk gate approves or rejects  
4. Transport carries only approved payloads  
5. Audit records the path  

**More agents do not mean more authority.**

**Swarm behavior is survivable only when every agent is bounded by the same validation path.**

---

## Safety posture

- Paper-only execution path; fail-closed gates
- No live trading logic in capstone rules
- No broker/network I/O without an explicit packet
- Schemas and playbooks are contracts—do not bypass or re-derive protected fields in automation
- MCP remains transport-only; real paper MCP requires an explicit future packet

---

## Repository navigation

| Doc | Topic |
|-----|--------|
| [docs/system-identity.md](./docs/system-identity.md) | Identity, structure policy, ML/subagent policy |
| [docs/claude-overlay.md](./docs/claude-overlay.md) | Claude overlay (memo-only) |
| [docs/claude-backtest-wiring.md](./docs/claude-backtest-wiring.md) | Claude backtest (research only) |
| [integrations/alpaca_mcp/README.md](./integrations/alpaca_mcp/README.md) | Alpaca MCP scaffold & posture |
| [integrations/alpaca_mcp/transport_contract.md](./integrations/alpaca_mcp/transport_contract.md) | C10A transport contract |
| [diagrams/claude_context_layer.md](./diagrams/claude_context_layer.md) | Context layer placement |
