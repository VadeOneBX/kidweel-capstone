# Claude Privacy + Authority Check

Packet: CLAUDE-PRIVACY-SUBAGENT-BT-C1 (Part 1). Advisory-only audit; no MCP or broker actions.

## Files inspected

- `.gitignore`
- `AGENTS.md`
- `CLAUDE.md`
- `docs/subagent-governance.md`
- `docs/claude-advisor-context.md`
- `docs/claude-backtest-wiring.md`
- `docs/claude-overlay.md`
- `.claude/agents/claude-advisor.md`
- `.claude/agents/safety-auditor.md`
- `.claude/skills/claude-advisor/SKILL.md` (path referenced from manifest; skill present in repo)
- `docs/system-identity.md` (spot-check for transport gate language)

## .gitignore result

- **Before packet:** `.claude/rules` was not listed in `.gitignore` (only `.cursor/rules/` was).
- **After packet fix:** `.claude/rules/` added under the Cursor/Claude local rules block.
- **Verification:** `git check-ignore -v .claude/rules/` → `.gitignore:247:.claude/rules/`

## .claude/rules status

- Directory **does not exist** in the working tree at audit time.
- **Not staged** (nothing under `.claude/rules` in `git status`).
- No content to leak; future local rules will be ignored once created.

## Authority boundary result

- `AGENTS.md` and `docs/subagent-governance.md` state: coordinator-only delegation; no approve, size, submit, close, cancel, replace, or route from agents.
- `docs/claude-advisor-context.md` lists forbidden actions (transport, MCP order tools, gate mutation).
- Agent manifests (`claude-advisor`, `safety-auditor`) repeat **warn, not act** posture.
- Doctrine preserved: transport only runs after payload approval; adding agents does not change the approval path; the system cannot skip the check.

## MCP risk result

- Advisory docs describe MCP as part of the **deterministic transport path**, not as a subagent default tool.
- Project agent tool lists are Read/Grep/Glob (safety-auditor adds Bash for audit commands only — manifest still forbids submit/close/cancel/replace).
- No new MCP submit/cancel/replace/close instructions were added in this packet’s allowed paths.

## Leak check result

- Grep for `.claude/rules` content in `docs/`, `src/`, and tracked files: **no copies** (directory absent).
- This audit does **not** paste any private rules content.

## Findings

1. `.claude/rules/` ignore rule was missing; corrected in `.gitignore`.
2. No `.claude/rules` directory present; privacy posture is **preventive** for future local rules.
3. Canonical advisory/authority docs align with bounded advisory — no execution grants found in inspected files.
4. Untracked trees outside packet scope (`alpaca-mcp-server/`, `.claude/worktrees/`) were not modified; note for manual hygiene (see refactor impact artifact).

## Required follow-up

- If operators create `.claude/rules/`, confirm `git status` never shows those paths before commit.
- Periodically re-run `git check-ignore -v .claude/rules/`.
- Keep untracked MCP server clones and Claude worktrees out of commits unless an approved implementation packet covers them.

## Final status

PASS_WITH_NOTES
