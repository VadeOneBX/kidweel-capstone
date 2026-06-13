# Agent policy (tool-agnostic)

Kidweel agents and skills are **bounded delegates** under the main coordinator. They do not own approval or transport.

**Doctrine:** Claude proposes; the system decides; transport executes. More agents do not mean more authority. Subagents help the system see; they do not help the system act.

Project rules: [CLAUDE.md](CLAUDE.md). Governance: [docs/subagent-governance.md](docs/subagent-governance.md).

---

## Policy

1. **Coordinator owns delegation.** Only the human-directed main session assigns agents, scope, and packet context.
2. **Agents do not spawn agents.** No nested Agent/Task trees.
3. **Agents do not gain execution authority.** No approve, size, submit, close, cancel, replace, or route orders from agent manifests or skills.
4. **Advisory may read supplied context.** Files, paste, and packet attachments named by the coordinator.
5. **Advisory may use read-only market / option info only when explicitly scoped** in the packet—not as default broker or MCP access.
6. **Paper transport remains repo-gated and explicit.** Gates, payloads, and MCP live on the deterministic path; not on advisory agents.
7. **Agents must use reference docs** listed in their bound skill’s Reference docs section.
8. **Missing references are blockers.** Report and stop; do not improvise architecture or data.

---

## Project agents

Manifests in [.claude/agents/](.claude/agents/). Each manifest binds one skill under [.claude/skills/](.claude/skills/).

| Agent | Manifest | Skill | Tools (manifest) |
|-------|----------|-------|------------------|
| repo-cleaner | [.claude/agents/repo-cleaner.md](.claude/agents/repo-cleaner.md) | repo-cleaner | Read, Grep, Glob |
| readme-editor | [.claude/agents/readme-editor.md](.claude/agents/readme-editor.md) | readme-editor | Read, Grep, Glob |
| safety-auditor | [.claude/agents/safety-auditor.md](.claude/agents/safety-auditor.md) | safety-auditor | Read, Grep, Glob, Bash |
| claude-advisor | [.claude/agents/claude-advisor.md](.claude/agents/claude-advisor.md) | claude-advisor | Read, Grep, Glob |

Invoke agents only through coordinator delegation. Skills enforce reference discipline and stop conditions.

---

## Non-negotiables (from governance)

- Only the main coordinator delegates.
- Subagents cannot spawn subagents.
- Advisory subagents do not receive paper transport access.
- No subagent may approve, size, submit, close, cancel, replace, or route orders.
- No subagent may modify gates or thresholds.
- If blocked, report and stop.
- Do not invent fallback behavior.
