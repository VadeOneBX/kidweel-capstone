#!/usr/bin/env bash
set -euo pipefail

echo "DEPRECATED: MCP-C1A reconciliation (Cursor copy) is retired."
echo "Use read-only MCP-C1C instead: bash scripts/diagnose_claude_mcp.sh"
echo "See docs/mcp_c1c_claude_mcp_diagnostic.md"
echo

exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/diagnose_claude_mcp.sh"
