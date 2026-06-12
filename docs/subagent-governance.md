# Subagent governance (SUBAGENT-GOV-C1)

Bounded subagent rules for Kidweel development and advisory workflows. Subagents provide **context isolation** and **specialized review**; they do **not** receive execution, approval, or transport authority.

**Governance chain:** [c13-governance.md](./c13-governance.md) → [system-identity.md](./system-identity.md) (ML / SUBAGENT POLICY) → this document for delegation mechanics. POLICY and STRUCTURE packets override platform defaults and informal agent behavior.

**Swarm-safe routing (unchanged):**

1. Agent proposes  
2. Deterministic validator checks  
3. Risk gate approves or rejects  
4. Transport carries only approved payloads  
5. Audit records the path  

More agents do not mean more authority.

---

## Purpose

Subagents are specialized workers for **bounded review, classification, and advisory** tasks. They run in isolated context (Cursor Task subagents, Claude Code Agent tool, or project-defined agents under `.cursor/agents/` / `.claude/agents/`). They may search, verify, document, audit, or advise. The **main coordinator** (human-directed top-level session) owns delegation and integrates results into the bounded validation path.

Subagents are **not** a second decision engine, approval path, or transport layer.

---

## Non-negotiables

1. Only the main coordinator delegates.
2. Subagents cannot spawn subagents.
3. Advisory subagents do not receive paper transport access.
4. No subagent may approve, size, submit, close, cancel, replace, or route orders.
5. No subagent may modify gates or thresholds.
6. If blocked, report and stop.
7. Do not invent fallback behavior.

---

## Subagent spawn policy

Subagents are used for bounded review, classification, and advisory tasks.

Only the main coordinator may delegate work.

Subagents may not spawn additional subagents.

Subagents may not call Alpaca paper transport, submit orders, close positions, cancel orders, mutate approval gates, or change PMP / reward-risk policy.

If a subagent encounters missing context, test failure, credential ambiguity, or scope conflict, it must report the blocker and stop.

No subagent may continue by inventing fallback behavior.

### Platform enforcement

**Coordinator-only delegation:** The main coordinator assigns each subagent a bounded task, explicit file/path scope, and required output shape. The subagent returns a final report; the coordinator decides next steps.

**No nesting:** Kidweel adopts the strict rule above even when the host product allows nested subagents (e.g. Cursor 2.5+).

| Platform | Enforcement |
|----------|-------------|
| **Claude Code** | Omit `Agent` from subagent `tools`. Do not add `Agent` to custom project agents. Optional: `permissions.deny` for `Agent` on project subagents. |
| **Cursor** | Custom Kidweel agents must not use Task to spawn children. Coordinator must not prompt a subagent to “dispatch subagents,” “run agents in parallel,” or “resume and spawn.” |
| **Custom stubs** | Prompt body must state: do not spawn subagents; return one report to the coordinator. |

**Built-in subagents:** Cursor built-ins (Explore, Bash, Browser) and Claude built-ins (Explore, Plan, general-purpose where applicable) run only when the coordinator delegates them. They remain subject to the spawn policy (e.g. Bash must not run paper submit, `--submit-paper`, or live Alpaca CLI).

**Resume:** Resuming a subagent by ID is allowed only when the coordinator explicitly continues the **same** subagent for the **same** bounded task—not to build a delegation tree.

---

## Reference discipline

Every subagent skill must name its reference docs.

A subagent may not expand beyond those docs unless the coordinator supplies additional context in the packet.

Missing references are blockers, not invitations to improvise.

Reference docs are used to reduce generic output, prevent architecture drift, and keep subagency bounded.

When the coordinator delegates, the task packet should list the same references the skill names. If a required doc is unavailable or not cited, the subagent reports the gap and stops per the [Subagent spawn policy](#subagent-spawn-policy).

### Default reference docs by role

| Role | Reference docs (minimum) |
|------|---------------------------|
| **repo-cleaner** | [subagent-governance.md](./subagent-governance.md), [.cursor/rules/capstone-repo.mdc](../.cursor/rules/capstone-repo.mdc) |
| **readme-editor** | [subagent-governance.md](./subagent-governance.md), [system-identity.md](./system-identity.md), [c13-governance.md](./c13-governance.md) |
| **safety-auditor** | [subagent-governance.md](./subagent-governance.md), [system-identity.md](./system-identity.md#alpaca-credential-and-paper-safety), [alpaca-paper-bridge.md](./alpaca-paper-bridge.md) |
| **test-verifier** | [subagent-governance.md](./subagent-governance.md), [c13-governance.md](./c13-governance.md); tests and packet scope named by coordinator |
| **advisory-analyst** | [subagent-governance.md](./subagent-governance.md), [claude-overlay.md](./claude-overlay.md), [system-identity.md](./system-identity.md#structure-policy) |

Versioned stubs under `.cursor/agents/` or `.claude/agents/` must repeat the role’s reference doc list in the prompt body.

---

## Allowed use cases

Use subagents when the coordinator needs **isolated context** or **parallel independent** work, not when a single skill or one-shot edit suffices.

| Use case | What the subagent may do | Returns to coordinator |
|----------|--------------------------|-------------------------|
| Explore / read | Codebase search, doc discovery, policy citation | Summary + paths; no gate changes |
| Verification | Run tests; confirm claimed work skeptically | Pass/fail evidence; gaps listed |
| Docs-only edits | Update `docs/`, `README.md`, diagrams per packet | Diff scope or completion report |
| Repo hygiene | Format, lint, unused imports in **coordinator-scoped** paths | List of files touched |
| Safety audit | Read-only review of secrets, auth, paper-only posture | Findings by severity |
| Advisory analysis | Memos, caution flags, canonical spread alternatives, recommend `SKIP` or confidence downgrade | Advisory text only; see [claude-overlay.md](./claude-overlay.md) |
| Parallel workstreams | Multiple subagents on **independent** tasks | One report each; coordinator merges |

Coordinator-initiated parallel Task calls are allowed. Subagents must not initiate their own parallel fan-out or nested delegation.

---

## Forbidden authority

Subagents and ML-style review share the same bounds as [system-identity.md](./system-identity.md#ml--subagent-policy). Additionally, subagents must **not** edit, invoke, or bypass:

| Area | Representative modules (read-only reference for scope) |
|------|--------------------------------------------------------|
| Execution / transport | `src/qops/execution/` (e.g. `alpaca_paper_bridge`, `mcp_gate`, `mock_transport`, `paper_order_status`, `paper_position_audit`, `mcp_adapter`) |
| Approval / payloads | `src/qops/risk/approval.py`, `paper_approval.py`, `src/qops/execution/payload.py`, `paper_payload_candidate.py`, `gate.py` |
| Spread math / structure emits | `src/qops/strategy/spread_math.py`, `spread_builder.py`, playbook emit set |
| PMP / RR policy | `src/qops/risk/pmp_policy.py`, `pmp_proxy.py`, `rr_audit.py` |
| Closeout | `src/qops/execution/paper_closeout.py`, `spread_close_pricing.py` |
| Playbooks / thresholds | Mutating `allowed_playbook`, structure bias upgrades, centralized constants, or gate thresholds |

Forbidden actions include: approve trades; override gates; create or mutate execution payloads; call broker or MCP order transport; mutate thresholds; bypass risk guard; upgrade `structure_bias`; change `SKIP` to an executable structure.

Schemas and playbooks are contracts—subagents do not rename fields, assume undocumented fields, or re-derive protected values (`regime_label`, `confidence`, `gamma_ratio`).

---

## MCP scoping policy

MCP is **transport-only** in this repo; approval lives in the repo. Subagents must not widen MCP beyond Kidweel’s narrowed surface ([tool_surface.md](../integrations/alpaca_mcp/tool_surface.md)).

### Defaults

- **Advisory and custom Kidweel subagents:** default **no MCP**. Read the codebase and docs locally.
- **Paper transport / order MCP:** **coordinator-only** if ever enabled for an approved packet. Never attach paper order or account-mutation MCP to advisory subagents.

### Platform behavior

| Platform | Kidweel rule |
|----------|--------------|
| **Claude Code** | Use minimal or empty `mcpServers` on advisory agents. Never inline Alpaca order servers on subagents. Scoped servers still obey enterprise / `allowedMcpServers` / `deniedMcpServers` policies. |
| **Cursor** | Subagents **inherit** parent MCP tools. Coordinator must not run advisory subagents in a session where Alpaca MCP is enabled for order actions, or must disable/limit MCP for that workflow. |

### Forbidden MCP classes (all subagents unless explicit future packet)

Live orders; cancel/replace; position liquidation; portfolio mutation beyond gated single paper transport; watchlists; crypto; research tools that substitute for the deterministic decision chain. See [tool_surface.md](../integrations/alpaca_mcp/tool_surface.md).

**Advisory subagents do not receive paper transport access.**

---

## Stop conditions

Stop immediately and **report to the coordinator** when any of the following occur. Do not retry in ways that submit orders, weaken gates, or invent alternate paths.

| Condition | Required behavior |
|-----------|-------------------|
| Missing context | Report; stop (see [Reference discipline](#reference-discipline)) |
| Test failure | Report; stop unless coordinator scoped a fix packet outside forbidden modules |
| Credential ambiguity | Report; stop |
| Scope conflict | Report; stop |
| Missing or invalid credentials | Report; stop (e.g. Alpaca CLI exit code 2 = auth failure; fix credentials before retry) |
| Gate or playbook denial | Report reason; stop |
| Schema / playbook conflict | Report; stop |
| POLICY / STRUCTURE ambiguity | Report; stop; do not derive from legacy canonicals or threads |
| Tool or MCP blocked | Report; stop |
| Task requires forbidden authority | Report; stop |
| User or coordinator revokes scope | Stop |

**Do not invent fallback behavior** (no alternate brokers, no mock submit to “unblock,” no threshold edits, no blind auth retry).

**test-verifier:** On test failure, report failures and logs. Implement fixes **only** if the coordinator scoped a fix packet and paths exclude forbidden modules.

---

## Project subagent roles (first five)

Define these in version control under `.cursor/agents/` (Cursor) or `.claude/agents/` (Claude compatibility) when the repo chooses to commit stubs. Names use lowercase hyphens.

### Summary table

| Role | Mission | Cursor `readonly` | Tools / MCP |
|------|---------|-------------------|-------------|
| **repo-cleaner** | Format, lint, remove unused imports; non-behavioral cleanup in scoped dirs | `true` unless coordinator allows writes in scope | File edit in scoped paths only; no order submit shell; **no MCP** |
| **readme-editor** | Docs and navigation accuracy | `true` or write limited to `docs/`, `README.md`, `diagrams/` | Read, search; **no MCP**; no `src/qops/execution/` edits |
| **safety-auditor** | Read-only security and paper-only posture | `true` | Read, search; **no Alpaca MCP**; findings by severity |
| **test-verifier** | Run pytest / verification; skeptical pass-fail report | `true` for verify-only | Shell for tests; no `--submit-paper`; no transport scripts; **no MCP orders** |
| **advisory-analyst** | Context memo, caution, canonical spread alternatives, recommend `SKIP`/downgrade | `true` | Read, search; **no paper transport MCP**; no payloads or gates |

### repo-cleaner

**Mission:** Hygiene in coordinator-scoped paths (tests, examples, non-execution modules).

**May:** Apply formatter/linter fixes; remove unused imports; small clarity edits that do not change gate behavior.

**May not:** Touch execution, approval, payload, spread math, PMP, closeout, or Alpaca transport code without an approved implementation packet assigned to the coordinator.

**Coordinator hint:** “Use repo-cleaner on `tests/` and `examples/` only; report files changed.”

### readme-editor

**Mission:** Keep documentation aligned with repo behavior and navigation tables.

**May:** Edit markdown under `docs/`, root `README.md`, and `diagrams/` when accurate.

**May not:** Change runtime behavior; edit forbidden modules above; imply subagents have approval or transport authority.

**Coordinator hint:** “Use readme-editor to add a link to subagent-governance and fix the nav table.”

### safety-auditor

**Mission:** Read-only audit for hardcoded secrets, live endpoint usage, credential mixing (market vs paper), and capstone anti-patterns in [system-identity.md](./system-identity.md#alpaca-credential-and-paper-safety).

**May:** Report Critical / High / Medium findings with file references.

**May not:** Modify code; call MCP; run submit or live CLI flags.

**Coordinator hint:** “Run safety-auditor on changed files in this branch; readonly.”

### test-verifier

**Mission:** Independently verify that claimed work passes tests and matches spec ([verification-before-completion](https://cursor.com/docs/subagents) pattern).

**May:** Run `pytest` and other read-only verification commands; report pass/fail counts and failure excerpts.

**May not:** Submit paper orders; run enrichment/submit scripts with network submit flags unless coordinator explicitly scopes a non-transport check; spawn subagents.

**Coordinator hint:** “test-verifier: run tests for `tests/test_paper_order_status.py`; do not fix unless I say so.”

### advisory-analyst

**Mission:** Advisory layer aligned with [claude-overlay.md](./claude-overlay.md)—interpret context, flag deterioration, propose bounded alternatives within canonical structures only.

**May emit recommendations for:** `BULL_CALL_SPREAD`, `BEAR_PUT_SPREAD`, `BULL_PUT_CREDIT_SPREAD`, `BEAR_CALL_CREDIT_SPREAD`, `SKIP`.

**May not:** Approve, size, execute, create payloads, call transport, mutate gates/thresholds, or upgrade structure bias.

**Coordinator hint:** “advisory-analyst: memo on liquidity and RR deterioration; recommend SKIP if unclear.”

Each role prompt should repeat the [Non-negotiables](#non-negotiables), [Subagent spawn policy](#subagent-spawn-policy), [Reference discipline](#reference-discipline) (with named docs), and [Stop conditions](#stop-conditions).

---

## Platform references

External mechanics (file format, built-ins, MCP scoping APIs). **Kidweel non-negotiables override** permissive platform defaults where they conflict.

| Reference | URL |
|-----------|-----|
| Cursor Subagents | https://cursor.com/docs/subagents |
| Claude Code — scope MCP to a subagent | https://code.claude.com/docs/en/sub-agents#scope-mcp-servers-to-a-subagent |
| Cursor agent-compatibility plugin (illustrative review pattern only) | https://github.com/cursor/plugins/tree/a5cda8b561bb6536e880481734199a568cb647f4/agent-compatibility |

### Optional versioned stubs

When the team commits agent definitions, prefer `.cursor/agents/<role>.md` with YAML frontmatter (`name`, `description`, `model: inherit`, `readonly` as in the summary table). Mirror to `.claude/agents/` only if Claude Code compatibility is required. Stubs are optional; this governance doc is authoritative whether or not stubs exist.

---

## Related docs

- [system-identity.md](./system-identity.md#ml--subagent-policy) — ML / subagent advisory bounds  
- [claude-overlay.md](./claude-overlay.md) — overlay and advisory structures  
- [c13-governance.md](./c13-governance.md) — authority order  
- [integrations/alpaca_mcp/tool_surface.md](../integrations/alpaca_mcp/tool_surface.md) — MCP narrowing  
- [integrations/alpaca_mcp/transport_contract.md](../integrations/alpaca_mcp/transport_contract.md) — transport contract (coordinator path only)
