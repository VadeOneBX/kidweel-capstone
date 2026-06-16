# Workflow ownership (OWNERSHIP-HANDOFF-C1)

Explicit ownership across Coordinator, Cursor, Claude, subagents, MCP, and Admins. This document replaces informal “Cursor talks to Claude” chat with a **repo-mediated handoff protocol**.

**Authority chain:** [c13-governance.md](./c13-governance.md) → [system-identity.md](./system-identity.md) → [subagent-governance.md](./subagent-governance.md) → [AGENTS.md](../AGENTS.md) / [CLAUDE.md](../CLAUDE.md). SpotGamma agent mapping: [AGENT-MAP-C1_spotgamma_strategy.md](../AGENT-MAP-C1_spotgamma_strategy.md); [AGENT-MAP-C1a_corrections.md](../AGENT-MAP-C1a_corrections.md) supersedes C1 on conflict. Handoffs must cite these paths when the packet scopes SpotGamma / strategy-group roles; POLICY and STRUCTURE still win per [c13-governance.md](./c13-governance.md).

**Doctrine (required language):**

- **Cursor edits.** **Claude advises.** **Subagents produce memos.** **MCP answers narrow calls.** **Coordinator approves.** **Admins sign off.**
- **The repo is the message bus.**
- **Claude can compare arguments. It cannot move the order.**
- **Adding agents does not change the approval path.**
- **The system cannot skip the check.**

---

## 1. Purpose

Kidweel is a deterministic, paper-only decision system. Multiple tools and agents may participate in development and review, but **only one approval path** may gate transport. This document assigns **ownership** (who may do what) and **handoff shape** (how work crosses tool boundaries without smuggling authority).

Goals:

- Make approval, mutation, advisory, integration, and sign-off boundaries explicit.
- Require file-based handoffs under `docs/handoffs/` instead of implicit chat continuity.
- Ensure no advisory output becomes an execution payload and no natural-language request becomes an MCP action.

---

## 2. Ownership table

| Actor | Owns | Does not own |
|-------|------|----------------|
| **Coordinator** (human-directed main session) | Delegation, packet scope, **approval** for paper transport and implementation packets, integration of subagent reports | Repo writes by default (delegates to Cursor), advisory synthesis (delegates to Claude), MCP/broker transport |
| **Cursor** | **Repo mutation** in coordinator-scoped packets; local verification commands; applying approved doc/code changes | Approval, advisory primary synthesis, transport submit, gate/threshold changes without packet |
| **Claude** | **Advisory synthesis** — memos, ranked findings, `ADVISORY_*` status, bounded structure *proposals* per [claude-advisor-context.md](./claude-advisor-context.md) | Approve, size, submit, close, cancel, replace, route; MCP order tools; broker calls; schema/gate edits |
| **Subagents** | **Assigned memo artifacts** (audit, hygiene, verification reports) within skill reference docs | Spawn subagents; approval; transport; gate changes |
| **MCP** | **Narrow integration responses** on the coordinator-gated transport path only ([alpaca-paper-bridge.md](./alpaca-paper-bridge.md), [tool_surface.md](../integrations/alpaca_mcp/tool_surface.md)) | Approval, payload construction, advisory conclusions, ad-hoc actions from chat |
| **Admins** | **Sign-off** on packets that change posture (policy acknowledgment, production-adjacent doc baselines, explicit paper-submit packets when scoped) | Day-to-day delegation, repo edits, advisory synthesis |
| **Deterministic repo** | Spread math, RR/PMP, playbooks, validation, payload shape, audit trail | Interpretive market narrative |

**No agent owns transport authority.** Transport executes only after coordinator approval and repo gates pass.

---

## 3. Machine/tool responsibilities

| Tool | Responsibility |
|------|----------------|
| **Cursor** | Edit files; run bounded terminal checks (`pytest`, `git status`, scoped `grep`); fill handoff templates; run reconciliation checklists. Cursor edits — it does not approve trades. |
| **Claude (Claude Code / project Claude session)** | Read handoff-listed files; write advisory response files per [TEMPLATE_claude_to_cursor.md](./handoffs/TEMPLATE_claude_to_cursor.md). Claude advises — it does not mutate `src/` unless a separate implementation packet explicitly scopes Claude-side work (default: Cursor owns repo mutation). |
| **MCP (Alpaca paper bridge)** | Return integration results for narrowly scoped, repo-gated calls. MCP answers narrow calls — not open-ended chat commands. |
| **Repo CI / local pytest** | Verify contracts; not a second implementation or approval path. |

---

## 4. Subagent responsibilities

Subagents are bounded delegates under the Coordinator ([subagent-governance.md](./subagent-governance.md)).

- **Subagents produce memos** — classification, audit findings, test evidence, doc diffs in scope — and return **one report** to the Coordinator.
- Subagents do not spawn subagents.
- Subagents do not receive paper transport MCP by default.
- Project roles (repo-cleaner, readme-editor, safety-auditor, claude-advisor, etc.) are defined in [AGENTS.md](../AGENTS.md) and skill reference maps in [subagency-proof.md](./subagency-proof.md).

Missing context → report `missing_context` and stop; do not infer market data or architecture.

---

## 5. Approval boundary

Swarm-safe routing (unchanged):

1. Agent proposes  
2. Deterministic validator checks  
3. Risk gate approves or rejects (**Coordinator owns approval** at the human/policy layer; repo gates enforce mechanically)  
4. Transport carries only approved payloads  
5. Audit records the path  

- **No advisory output can become a payload.** Advisor memos and `ADVISORY_*` labels inform review; they do not short-circuit `approval.py`, paper gates, or payload builders.
- **Adding agents does not change the approval path.**
- **The system cannot skip the check.**

---

## 6. Repo-mediated handoff protocol

**The repo is the message bus.** Cross-tool work uses committed or packet-staged files, not chat memory alone.

1. **Coordinator** defines packet ID, scope, and allowed paths.
2. **Cursor** writes [TEMPLATE_cursor_to_claude.md](./handoffs/TEMPLATE_cursor_to_claude.md) and lists input paths under `docs/handoffs/` (or coordinator-named audit paths).
3. **Claude** reads only listed files; writes response per [TEMPLATE_claude_to_cursor.md](./handoffs/TEMPLATE_claude_to_cursor.md) to a coordinator-named path (typically under `docs/audit/` or `docs/handoffs/responses/`).
4. **Cursor** (or test-verifier subagent) runs [TEMPLATE_claude_response_check.md](./reconciliation/TEMPLATE_claude_response_check.md) before merging advisory conclusions into any implementation packet.
5. **Coordinator** decides next packet (docs-only, narrow code packet, or stop).

Chat may discuss the packet; **authoritative handoff content lives in the repo files** cited by packet ID.

See [handoffs/README.md](./handoffs/README.md).

---

## 7. MCP boundary

- MCP is **transport-only**; the repo owns approval ([subagent-governance.md#mcp-scoping-policy](./subagent-governance.md#mcp-scoping-policy)).
- **No natural-language query can become an MCP action.** MCP calls require an approved implementation packet, explicit coordinator intent, and repo gate wiring — not advisory or handoff prose.
- Advisory sessions (Claude, subagents) default to **no MCP**. Paper order/account mutation MCP is coordinator-scoped only.
- Forbidden for advisory handoffs: live endpoints, cancel/replace, blind portfolio mutation, using MCP to “fill in” missing market context.

---

## 8. Admin sign-off boundary

**Admins sign off** on explicit checkpoints — not on every advisory memo.

Typical sign-off surfaces (coordinator documents which apply per packet):

- Acknowledgment of POLICY / STRUCTURE / implementation packet authority before merge to protected branches.
- Paper-submit packets: human confirmation that gates, dry-run default, and `ALPACA_PAPER_*` posture were reviewed ([system-identity.md](./system-identity.md#alpaca-credential-and-paper-safety)).
- Baseline doc sets (governance, ownership, handoff templates) when used as course or audit deliverables.

Admins do not replace Coordinator approval for transport or substitute for deterministic validators.

---

## 9. Failure behavior

| Condition | Behavior |
|-----------|----------|
| Missing handoff files or references | Write `missing_context`; stop |
| Claude response cites disallowed authority | Reconciliation `RECON_FAIL`; do not treat as approval |
| MCP or broker language in advisory artifact | Reconciliation `RECON_FAIL`; coordinator investigates |
| Execution/schema/transport files changed without packet | Reconciliation `RECON_FAIL`; revert per coordinator |
| Test failure on verification | Report assertion; stop (do not patch gates to green) |
| POLICY / STRUCTURE conflict | Report; stop; C13 authority order applies |

Do not invent fallback behavior (synthetic data, alternate endpoints, threshold edits).

---

## 10. Forbidden actions

Across Coordinator, Cursor, Claude, subagents, and MCP handoff paths:

- Approve, size, submit, close, cancel, replace, or route orders from advisory or handoff artifacts.
- Turn advisory output into execution payloads.
- Issue MCP or broker actions from natural-language handoff text.
- Change gates, schemas, thresholds, or playbooks without an approved implementation packet.
- Re-derive protected fields (`regime_label`, `confidence`, `gamma_ratio`).
- Upgrade `structure_bias`; `SKIP` remains `SKIP`.
- Spawn subagents from subagents.
- Use live Alpaca trading endpoints or market-data keys for paper submit.
- Skip reconciliation when Claude response informs a merge or transport-adjacent packet.

---

## Related docs

- [handoffs/README.md](./handoffs/README.md) — file-based handoff rules  
- [claude-advisor-context.md](./claude-advisor-context.md) — Claude advisory labels  
- [subagent-governance.md](./subagent-governance.md) — subagent spawn and MCP policy  
- [alpaca-paper-bridge.md](./alpaca-paper-bridge.md) — paper transport contract  
