# MCP-C1A (retired)

MCP-C1A proposed copying Cursor MCP config into `.claude/settings.json`. That path is **retired**:

- Cursor project MCP was never the Claude source of truth here.
- Copying can **overwrite** an existing Claude config that already uses `${VAR}` env references.
- It does not diagnose failures after `source .venv/bin/activate && claude`.

## Use instead

**MCP-C1C** — read-only diagnostic:

```bash
bash scripts/diagnose_claude_mcp.sh
```

Documentation: [mcp_c1c_claude_mcp_diagnostic.md](mcp_c1c_claude_mcp_diagnostic.md)

`scripts/reconcile_claude_mcp.sh` remains as a thin wrapper that runs the C1C diagnostic and does not copy or write MCP config.
