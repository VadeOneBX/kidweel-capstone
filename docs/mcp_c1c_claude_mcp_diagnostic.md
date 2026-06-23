# MCP-C1C Claude MCP diagnostic (read-only)

Answers: when `source .venv/bin/activate && claude` is run from repo root, what prevents `/mcp` from connecting?

## Correction vs MCP-C1A

- Cursor MCP config is **not** the source of truth for Claude Code in this repo.
- `.claude/settings.json` may already exist with `${VAR}` env references (for example `${ALPACA_PAPER_KEY}`).
- **Do not** copy Cursor config into Claude config or overwrite `.claude/settings.json`.
- Failure class is usually **MCP runtime**: env interpolation, venv boundary, command path, config shape, or package mismatch—not missing `.cursor/mcp.json`.

## Scope

- Repo tooling only; read-only (no MCP config writes)
- No changes to `src`, gates, schemas, transport, or live/paper posture

## Files

- `scripts/diagnose_claude_mcp.sh`
- `docs/mcp_c1c_claude_mcp_diagnostic.md`

## Operator run (repo root)

```bash
bash scripts/diagnose_claude_mcp.sh
```

## What the script does

1. Resolves repo root (`git rev-parse` or `pwd`).
2. Requires `claude` on PATH (exit `2` if missing).
3. Requires `CLAUDE.md`, `AGENTS.md`, `.claude/agents` (exit `3` if missing).
4. Requires `.claude/settings.json` (exit `4` if missing).
5. Prints git status for settings: `tracked`, `ignored`, or `untracked_not_ignored`.
6. Parses MCP servers from settings (redacted): names, command, args, env keys; marks `${VAR}` as `REFERENCE` vs non-secret literals as `LITERAL_REDACTED`.
7. **Hard-fails** only on literal secret-like values in MCP env (not on `${ALPACA_PAPER_KEY}`-style references).
8. Prints shell env **presence** (no values) for Alpaca-related keys listed in the packet.
9. Prints availability of `claude`, `uv`, `uvx`, `node`, `python`, `python3`, `.venv/bin/python`, `alpaca`.
10. If `.venv` exists: Python version and alpaca-related module names (no secrets).
11. Prints the manual interactive test block (`source .venv/bin/activate`, `claude`, `/status`, `/agents`, `/mcp`).

## Interpreting output

| Symptom | Likely class |
|---------|----------------|
| `env_missing:*` for vars referenced in settings | Env resolution / interpolation |
| `missing:uvx` or wrong command in server block | Command path |
| `/status` OK, `/mcp` fails | MCP subprocess or package runtime |
| `mcp_servers:none` | Config shape / empty MCP block |

## Supersedes

`scripts/reconcile_claude_mcp.sh` (MCP-C1A copy path) is deprecated; use this diagnostic instead.
