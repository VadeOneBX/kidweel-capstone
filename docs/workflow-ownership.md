# Workflow ownership (OWNERSHIP-HANDOFF-C1)

Explicit ownership across **operator**, implementation surfaces (Cursor, Claude Code, Cursor mobile), advisory surfaces (claude-advisor, advisory agents, Claude.ai), subagents, MCP, and Admins. This document replaces informal “Cursor talks to Claude” chat with a **repo-mediated handoff protocol**.

**Surface taxonomy:** [CLAUDE.md](../CLAUDE.md#surface-taxonomy-authority-matters).

**Authority chain:** [c13-governance.md](./c13-governance.md) → [system-identity.md](./system-identity.md) → [subagent-governance.md](./subagent-governance.md) → [AGENTS.md](../AGENTS.md) / [CLAUDE.md](../CLAUDE.md). Bounded delegation (public): Agent work → Gate → Human review → Decision → Audit. POLICY and STRUCTURE still win per [c13-governance.md](./c13-governance.md).

**Doctrine (required language):**

- **Cursor edits.** **claude-advisor advises.** **Advisory agents produce memos.** **MCP answers narrow calls.** **Operator approves.** **Admins sign off.**
- **The repo is the message bus.**
- **Advisory can compare arguments. It cannot move the order.**
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
| **Operator** (human decision-maker) | Delegation, packet scope, **approval** for paper transport and implementation packets; canonical runtime commands | Advisory synthesis (delegates to claude-advisor), repo writes (delegates to Cursor) |
| **Cursor / Claude Code / Cursor Claude** | **Repo mutation** in coordinator-scoped packets; local verification commands; applying approved doc/code changes | Approval, advisory primary synthesis, transport submit, gate/threshold changes without packet |
| **Cursor mobile** | Mobile implementation/review for Cursor agents: scoped repo edits, diff review, and **review bundles** under `docs/audit/` in packets | Approval, transport, arbitrary shell, morning-loop submit, runtime authority |
| **claude-advisor** | **Advisory synthesis** — memos, ranked findings, `ADVISORY_*` status, bounded structure *proposals* per [claude-advisor-context.md](./claude-advisor-context.md) | Approve, size, submit, close, cancel, replace, route; MCP order tools; broker calls; schema/gate edits |
| **Claude.ai desktop / Claude mobile** | Artifact review; desktop may later trigger allowlisted operator commands | Approve, size, submit, bypass gates, arbitrary shell (mobile: review-only unless allowlisted) |
| **Advisory agents** (repo-cleaner, safety-auditor, etc.) | **Assigned memo artifacts** within skill reference docs | Spawn subagents; approval; transport; gate changes |
| **MCP** | **Narrow integration responses** on the operator-gated transport path only ([alpaca-paper-bridge.md](./alpaca-paper-bridge.md), [tool_surface.md](../integrations/alpaca_mcp/tool_surface.md)) | Approval, payload construction, advisory conclusions, ad-hoc actions from chat |
| **Admins** | **Sign-off** on packets that change posture (policy acknowledgment, production-adjacent doc baselines, explicit paper-submit packets when scoped) | Day-to-day delegation, repo edits, advisory synthesis |
| **Deterministic repo** | Spread math, RR/PMP, playbooks, validation, payload shape, audit trail | Interpretive market narrative |

**No agent owns transport authority.** Transport executes only after operator approval and repo gates pass.

---

## 3. Machine/tool responsibilities

| Tool | Responsibility |
|------|----------------|
| **Cursor / Claude Code / Cursor Claude** | Edit files; run bounded terminal checks (`pytest`, `git status`, scoped `grep`); fill handoff templates; run reconciliation checklists. Edits repo—it does not approve trades. |
| **Cursor mobile** | Mobile implementation/review for Cursor agents: scoped repo edits, diff review, committed **review bundles** (`docs/audit/*_bundle.md`)—no transport or gate changes. |
| **claude-advisor** (coordinator-delegated skill) | Read handoff-listed files; write advisory response files per [TEMPLATE_claude_to_cursor.md](./handoffs/TEMPLATE_claude_to_cursor.md). Advises—it does not mutate `src/` unless a separate implementation packet explicitly scopes that work (default: Cursor owns repo mutation). |
| **Claude.ai desktop / Claude mobile** | Review artifacts; desktop may later use allowlisted operator commands. Mobile is visibility/review only unless routed through the same boundary. Neither approves or submits. |
| **MCP (Alpaca paper bridge)** | Return integration results for narrowly scoped, repo-gated calls. MCP answers narrow calls—not open-ended chat commands. |
| **Repo CI / local pytest** | Verify contracts; not a second implementation or approval path. |
| **Operator runtime** (host shell, SSH/Tailscale) | Run canonical commands (`orb_morning_loop.py`, `operator_status.py`, paper CLIs when packeted)—distinct from IDE/mobile chat surfaces. |

---

## 4. Subagent responsibilities

Subagents are bounded delegates under the **operator** ([subagent-governance.md](./subagent-governance.md)).

- **Advisory agents produce memos** — classification, audit findings, test evidence, doc diffs in scope — and return **one report** to the operator.
- Subagents do not spawn subagents.
- Subagents do not receive paper transport MCP by default.
- Project roles (repo-cleaner, readme-editor, safety-auditor, claude-advisor, etc.) are defined in [AGENTS.md](../AGENTS.md) and skill reference maps in [subagency-proof.md](./subagency-proof.md).

Missing context → report `missing_context` and stop; do not infer market data or architecture.

---

## 5. Approval boundary

Swarm-safe routing (unchanged):

1. Agent proposes  
2. Deterministic validator checks  
3. Risk gate approves or rejects (**operator** owns approval at the human/policy layer; repo gates enforce mechanically)  
4. Transport carries only approved payloads  
5. Audit records the path  

- **No advisory output can become a payload.** Advisor memos and `ADVISORY_*` labels inform review; they do not short-circuit `approval.py`, paper gates, or payload builders.
- **Adding agents does not change the approval path.**
- **The system cannot skip the check.**

---

## 6. Repo-mediated handoff protocol

**The repo is the message bus.** Cross-tool work uses committed or packet-staged files, not chat memory alone.

1. **Operator** defines packet ID, scope, and allowed paths.
2. **Cursor** writes [TEMPLATE_cursor_to_claude.md](./handoffs/TEMPLATE_cursor_to_claude.md) and lists input paths under `docs/handoffs/` (or operator-named audit paths).
3. **claude-advisor** (or coordinator-scoped Claude.ai session per packet) reads only listed files; writes response per [TEMPLATE_claude_to_cursor.md](./handoffs/TEMPLATE_claude_to_cursor.md) to an operator-named path (typically under `docs/audit/` or `docs/handoffs/responses/`).
4. **Cursor** (or test-verifier advisory agent) runs [TEMPLATE_claude_response_check.md](./reconciliation/TEMPLATE_claude_response_check.md) before merging advisory conclusions into any implementation packet.
5. **Operator** decides next packet (docs-only, narrow code packet, or stop).

Chat may discuss the packet; **authoritative handoff content lives in the repo files** cited by packet ID.

See [handoffs/README.md](./handoffs/README.md).

### Cursor mobile review bundles

When a packet is executed on **Cursor mobile**, chat export is unreliable. **Commit a review bundle** under `docs/audit/` before closeout ([cursor_mobile_pack_contract.md](./cursor_mobile_pack_contract.md#mobile-review-bundle-required-for-implementationreview-packs), [audit/README.md](./audit/README.md)).

- **Owner:** Cursor / Cursor mobile agent (writes bundle); operator reviews on mobile or GitHub.
- **Shape:** Markdown with packet name, branch, commit, PR, scope, changed files, acceptance checklist, authority after merge, per-file summary, out-of-scope confirmation, mobile review path, export commands.
- **Not a substitute for:** handoff templates, reconciliation checklists, or operator runtime commands.
- **Example:** [taxonomy_normalization_bundle.md](./audit/taxonomy_normalization_bundle.md)

---

## 7. MCP boundary

- MCP is **transport-only**; the repo owns approval ([subagent-governance.md#mcp-scoping-policy](./subagent-governance.md#mcp-scoping-policy)).
- **No natural-language query can become an MCP action.** MCP calls require an approved implementation packet, explicit coordinator intent, and repo gate wiring — not advisory or handoff prose.
- Advisory sessions (claude-advisor, advisory agents, Claude.ai review) default to **no MCP**. Paper order/account mutation MCP is operator-scoped only.
- Forbidden for advisory handoffs: live endpoints, cancel/replace, blind portfolio mutation, using MCP to “fill in” missing market context.

---

## 8. Admin sign-off boundary

**Admins sign off** on explicit checkpoints — not on every advisory memo.

Typical sign-off surfaces (operator documents which apply per packet):

- Acknowledgment of POLICY / STRUCTURE / implementation packet authority before merge to protected branches.
- Paper-submit packets: human confirmation that gates, dry-run default, and `ALPACA_PAPER_*` posture were reviewed ([system-identity.md](./system-identity.md#alpaca-credential-and-paper-safety)).
- Baseline doc sets (governance, ownership, handoff templates) when used as course or audit deliverables.

Admins do not replace operator approval for transport or substitute for deterministic validators.

---

## 9. Failure behavior

| Condition | Behavior |
|-----------|----------|
| Missing handoff files or references | Write `missing_context`; stop |
| claude-advisor response cites disallowed authority | Reconciliation `RECON_FAIL`; do not treat as approval |
| MCP or broker language in advisory artifact | Reconciliation `RECON_FAIL`; coordinator investigates |
| Execution/schema/transport files changed without packet | Reconciliation `RECON_FAIL`; revert per coordinator |
| Test failure on verification | Report assertion; stop (do not patch gates to green) |
| POLICY / STRUCTURE conflict | Report; stop; C13 authority order applies |

Do not invent fallback behavior (synthetic data, alternate endpoints, threshold edits).

---

## 10. Forbidden actions

Across operator, Cursor, Cursor mobile, claude-advisor, Claude.ai surfaces, advisory agents, and MCP handoff paths:

- Approve, size, submit, close, cancel, replace, or route orders from advisory or handoff artifacts.
- Turn advisory output into execution payloads.
- Issue MCP or broker actions from natural-language handoff text.
- Change gates, schemas, thresholds, or playbooks without an approved implementation packet.
- Re-derive protected fields (`regime_label`, `confidence`, `gamma_ratio`).
- Upgrade `structure_bias`; `SKIP` remains `SKIP`.
- Spawn subagents from subagents.
- Use live Alpaca trading endpoints or market-data keys for paper submit.
- Skip reconciliation when claude-advisor response informs a merge or transport-adjacent packet.

---

## Related docs

- [handoffs/README.md](./handoffs/README.md) — file-based handoff rules  
- [claude-advisor-context.md](./claude-advisor-context.md) — claude-advisor labels  
- [CLAUDE.md](../CLAUDE.md#surface-taxonomy-authority-matters) — surface taxonomy
- [subagent-governance.md](./subagent-governance.md) — subagent spawn and MCP policy  
- [cursor_mobile_pack_contract.md](./cursor_mobile_pack_contract.md) — Cursor mobile pack + review bundle contract  
- [audit/README.md](./audit/README.md) — audit directory and bundle standard  
