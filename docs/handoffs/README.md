# Handoffs (repo-mediated)

How Coordinator, Cursor, and Claude exchange work **through the repository**, not through implicit chat state.

**Parent:** [workflow-ownership.md](../workflow-ownership.md) (OWNERSHIP-HANDOFF-C1).

---

## 1. Why handoffs are file-based

- **The repo is the message bus.** Packet ID, inputs, and outputs must be diffable, reviewable, and auditable.
- Chat tools do not share memory across sessions; files do.
- Reconciliation ([TEMPLATE_claude_response_check.md](../reconciliation/TEMPLATE_claude_response_check.md)) requires stable paths and explicit “allowed input files.”
- **No advisory output can become a payload** — separating handoff files from `src/qops/execution/` and payload modules keeps authority visible in `git diff`.

---

## 2. Allowed handoff direction

| Direction | Sender | Recipient | Typical artifact |
|-----------|--------|-----------|------------------|
| Request advisory | Cursor (on Coordinator packet) | Claude | `TEMPLATE_cursor_to_claude.md` + listed inputs |
| Advisory response | Claude | Cursor / Coordinator | `TEMPLATE_claude_to_cursor.md` |
| Subagent memo | Subagent | Coordinator | Skill-defined memo under `docs/audit/` or packet path |
| Reconciliation | Cursor or test-verifier | Coordinator | `TEMPLATE_claude_response_check.md` |

**Not allowed:** Claude → broker, Claude → MCP orders, subagent → subagent delegation tree, chat-only “approved” language without repo gates.

Handoffs are **docs and advisory** unless a separate **implementation packet** explicitly scopes Cursor edits in `src/`.

---

## 3. Cursor to Claude

1. Coordinator assigns packet ID and objective.
2. Cursor copies [TEMPLATE_cursor_to_claude.md](./TEMPLATE_cursor_to_claude.md) to a named file, e.g. `docs/handoffs/<packet_id>_cursor_to_claude.md`.
3. Fill **Allowed input files** and **Required source-of-truth files** (POLICY, STRUCTURE, plus audit inputs). Public delegation stays abstract: Agent work → Gate → Human review → Decision → Audit.
4. Set **Required output file** path for Claude’s response.
5. Commit or stage per coordinator practice so Claude reads the same revision.

Cursor edits the handoff request; Claude does not mutate the request file unless the coordinator explicitly scopes a doc fix.

---

## 4. Claude to Cursor

1. Claude reads **only** paths listed in the handoff (and required source-of-truth docs).
2. Claude writes the response using [TEMPLATE_claude_to_cursor.md](./TEMPLATE_claude_to_cursor.md) at the **Required output file** path.
3. Status must be one of: `ADVISORY_OK`, `ADVISORY_CAUTION`, `ADVISORY_DOWNGRADE`, `ADVISORY_SKIP` ([claude-advisor-context.md](../claude-advisor-context.md)).
4. **Recommended repo action** is limited to: Docs only / narrow packet / no action.
5. If data is missing, list paths under **Missing context** and use `missing_context` behavior — do not infer market data.

Claude advises; Cursor applies doc or code changes only per coordinator follow-up packets.

---

## 5. Validation

Before treating Claude output as input to further work:

1. Run [TEMPLATE_claude_response_check.md](../reconciliation/TEMPLATE_claude_response_check.md).
2. Confirm **Forbidden authority language** absent (approve, submit, route, etc. as imperatives on orders).
3. Confirm no **MCP calls** or **broker calls** in the advisory artifact.
4. Confirm `src/`, execution, schema, and transport paths unchanged unless a separate implementation packet allowed them.

Final status: `RECON_PASS`, `RECON_PASS_WITH_NOTES`, or `RECON_FAIL`.

**The system cannot skip the check.**

---

## 6. Retention / audit

- Handoff requests and responses live under `docs/handoffs/` and coordinator-named `docs/audit/` paths.
- Reconciliation records live under `docs/reconciliation/`.
- Packet ID should appear in all three for traceability.
- Mock and course artifacts (e.g. `mock_*_C1.md`) follow the same shape for dry-run workflows.
- Do not commit secrets, `.env`, or `data/processed` broker CSVs.

Audit narrative: advisory informed review; transport and approval remain on the deterministic path ([subagent-governance.md](../subagent-governance.md)).

---

## 7. Forbidden shortcuts

- Pasting Claude chat as a substitute for a filled `TEMPLATE_claude_to_cursor.md`.
- “Cursor talks to Claude” in DMs without repo files and packet ID.
- Using Claude **Recommended repo action** to justify submit, `--submit-paper`, or MCP order tools.
- Expanding **Allowed input files** after Claude wrote the response without a new handoff revision.
- Subagents writing handoff responses meant for Claude’s advisory synthesis role (claude-advisor owns that skill boundary).
- Natural-language instructions to “just call MCP” or “place the order” — **no natural-language query can become an MCP action.**

---

## Templates

| File | Use |
|------|-----|
| [TEMPLATE_cursor_to_claude.md](./TEMPLATE_cursor_to_claude.md) | Outbound advisory request |
| [TEMPLATE_claude_to_cursor.md](./TEMPLATE_claude_to_cursor.md) | Inbound advisory response |
| [TEMPLATE_claude_response_check.md](../reconciliation/TEMPLATE_claude_response_check.md) | Reconciliation |
