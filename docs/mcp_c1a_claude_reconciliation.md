# MCP-C1A Claude MCP reconciliation

This packet adds a repo-local operator script to reconcile Claude MCP config with the canonical repo source at `.cursor/mcp.json`.

## Scope

- Repo tooling only
- No execution-path changes
- No gate/schema/transport behavior changes

## Files

- `scripts/reconcile_claude_mcp.sh`
- `docs/mcp_c1a_claude_reconciliation.md`

## Operator run (repo root)

```bash
bash scripts/reconcile_claude_mcp.sh
```

## What the script does

1. Resolves and prints repo root.
2. Prints whether `claude` command exists.
3. Prints whether `CLAUDE.md`, `AGENTS.md`, `.claude/agents`, and `.claude/settings.json` exist.
4. Requires `.cursor/mcp.json`.
5. Copies `.cursor/mcp.json` to `.claude/settings.json`.
6. Fails if inline credential-like Alpaca content is detected in `.claude/settings.json`.
7. Runs `claude /doctor` when available, or surfaces that `claude` is missing.
8. Prints manual Claude smoke-test commands:
   - `/status`
   - `/agents`
   - `/mcp`
   - `safety-auditor` review of `CLAUDE.md`, `AGENTS.md`, and `.claude/settings.json`

## Verification notes

- Script is runnable from repo root via `bash`.
- Script is idempotent for repeated reconciliation.
- Script only updates `.claude/settings.json` from `.cursor/mcp.json`.
