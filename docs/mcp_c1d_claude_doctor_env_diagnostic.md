# MCP-C1D Claude Doctor MCP environment diagnostic

Read-only tooling to separate **global Claude settings contamination** from **valid project MCP config** and **same-shell env** issues. Does not copy Cursor config or write any settings file.

## Why this pack exists

Claude `/doctor` can report malformed `~/.claude/settings.json`. Malformed global settings are **skipped entirely**, which can block MCP even when `.claude/settings.json` in the repo is valid with `${ALPACA_PAPER_KEY}` / `${ALPACA_PAPER_SECRET}` references.

## Scope

- Repo tooling only
- No changes to `src`, gates, schemas, transport, or live/paper posture
- Never prints secret values

## Files

- `scripts/diagnose_claude_doctor_env.sh`
- `docs/mcp_c1d_claude_doctor_env_diagnostic.md`

## Operator run (repo root)

```bash
source .venv/bin/activate
# load paper env in this same shell
bash scripts/diagnose_claude_doctor_env.sh
```

## Files inspected (never mutated)

| Label | Path |
|--------|------|
| Global Claude | `~/.claude/settings.json` |
| Project Claude | `.claude/settings.json` |
| Global Cursor | `~/.cursor/mcp.json` |
| Project Cursor | `.cursor/mcp.json` |

For each file: `VALID_JSON` / `MALFORMED_JSON` / `MISSING`, MCP server names, command, args, env keys, and env value class (`REFERENCE`, `LITERAL_SECRET_DETECTED`, `NON_SECRET_LITERAL`).

## Precedence signals

| Signal | Meaning |
|--------|---------|
| `GLOBAL_MALFORMED_BLOCKER` | Fix global JSON before trusting any MCP load |
| `PROJECT_VALID` | Project settings parse and are usable |
| `DUPLICATE_SERVER_WARNING` | Same MCP server name in global and project settings |

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | No blockers detected |
| 2 | `claude` missing |
| 3 | Malformed global Claude settings |
| 4 | Project settings missing or malformed |
| 5 | Inline secret literals in MCP env |
| 6 | Required runtime missing (`uv`, `uvx`, `python3`, `git`) |
| 7 | Both `ALPACA_PAPER_KEY` and `ALPACA_PAPER_SECRET` missing in launch shell |

## Related

- [mcp_c1c_claude_mcp_diagnostic.md](mcp_c1c_claude_mcp_diagnostic.md) — project-focused MCP diagnostic (C1C)
- [github_branch_reconciliation_pr_runbook.md](github_branch_reconciliation_pr_runbook.md) — branch audit and PR path to `main` (C1D commit 2)
