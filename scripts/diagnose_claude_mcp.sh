#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "${ROOT}"

echo "== Kidweel Claude MCP Diagnostic (MCP-C1C) =="
echo "repo_root=${ROOT}"

echo
echo "1) Claude Code"
if command -v claude >/dev/null 2>&1; then
  echo "found:claude=$(command -v claude)"
  claude --version 2>/dev/null || true
else
  echo "HARD_FAIL:claude_not_found"
  exit 2
fi

echo
echo "2) Repo footing"
for f in CLAUDE.md AGENTS.md; do
  if [[ -f "${f}" ]]; then
    echo "found:${f}"
  else
    echo "HARD_FAIL:missing:${f}"
    exit 3
  fi
done

if [[ -d ".claude/agents" ]]; then
  echo "found:.claude/agents"
  ls .claude/agents
else
  echo "HARD_FAIL:missing:.claude/agents"
  exit 3
fi

echo
echo "3) Claude MCP config"
if [[ ! -f ".claude/settings.json" ]]; then
  echo "HARD_FAIL:missing:.claude/settings.json"
  exit 4
fi

echo "found:.claude/settings.json"

if git ls-files --error-unmatch .claude/settings.json >/dev/null 2>&1; then
  echo "git_status:tracked"
elif git check-ignore -q .claude/settings.json 2>/dev/null; then
  echo "git_status:ignored"
else
  echo "git_status:untracked_not_ignored"
fi

echo
echo "4) Redacted MCP config summary"
mcp_summary="$(python3 - <<'PY'
import json
import re
import sys
from pathlib import Path

p = Path(".claude/settings.json")
try:
    data = json.loads(p.read_text())
except json.JSONDecodeError as e:
    print(f"HARD_FAIL:invalid_json:{e}")
    sys.exit(5)

servers = data.get("mcpServers") or data.get("mcp_servers") or {}

if not servers:
    print("mcp_servers:none")
    raise SystemExit(0)

ref_pat = re.compile(r"^\$\{[^}]+\}$")
literal_secret = 0

def looks_like_secret(key: str, value: str) -> bool:
    if ref_pat.match(value):
        return False
    ku = key.upper()
    if "SECRET" in ku or "PASSWORD" in ku or "TOKEN" in ku:
        return len(value.strip()) > 0
    if "KEY" in ku or "API" in ku:
        if value.startswith("PK") or value.startswith("AKIA") or value.startswith("sk-"):
            return True
        if len(value) >= 16 and value.isalnum():
            return True
    return False

for name, cfg in servers.items():
    print(f"server:{name}")
    print(f"  command:{cfg.get('command')}")
    print(f"  args:{cfg.get('args')}")
    env = cfg.get("env") or {}
    if not env:
        print("  env:none")
        continue
    for k, v in env.items():
        if isinstance(v, str) and ref_pat.match(v):
            print(f"  env:{k}=REFERENCE:{v}")
        elif isinstance(v, str):
            if looks_like_secret(k, v):
                print(f"  env:{k}=LITERAL_SECRET_DETECTED")
                literal_secret = 1
            else:
                print(f"  env:{k}=LITERAL_REDACTED")
        else:
            print(f"  env:{k}=NONSTRING_REDACTED")

if literal_secret:
    print("HARD_FAIL:inline_secret_literals_in_mcp_env")
PY
)"
echo "${mcp_summary}"
literal_fail=0
if echo "${mcp_summary}" | grep -q 'HARD_FAIL:inline_secret_literals_in_mcp_env'; then
  literal_fail=1
fi

echo
echo "5) Shell env presence (names only)"
for k in \
  ALPACA_PAPER_KEY \
  ALPACA_PAPER_SECRET \
  ALPACA_API_KEY \
  ALPACA_SECRET_KEY \
  ALPACA_PAPER_TRADE \
  ALPACA_TOOLSETS
do
  if [[ -n "${!k:-}" ]]; then
    echo "env_present:${k}"
  else
    echo "env_missing:${k}"
  fi
done

echo
echo "6) Runtime commands"
for c in claude uv uvx node python python3 alpaca; do
  if command -v "${c}" >/dev/null 2>&1; then
    echo "found:${c}=$(command -v "${c}")"
  else
    echo "missing:${c}"
  fi
done

if [[ -x ".venv/bin/python" ]]; then
  echo "found:.venv/bin/python=${ROOT}/.venv/bin/python"
  .venv/bin/python --version 2>/dev/null || true
  .venv/bin/python - <<'PY' 2>/dev/null || true
import pkgutil
mods = sorted(m.name for m in pkgutil.iter_modules() if "alpaca" in m.name.lower())
print("alpaca_related_modules=" + ",".join(mods) if mods else "alpaca_related_modules=none")
PY
else
  echo "missing:.venv/bin/python"
fi

echo
echo "7) Manual Claude MCP test"
cat <<'PROMPT'
Run exactly:

source .venv/bin/activate
claude

Inside Claude Code:

/status
/agents
/mcp

Expected interpretation:
- If /status and /agents pass but /mcp fails, the problem is MCP runtime/config/env, not repo footing.
- Capture the MCP server name, command, args, and error text.
PROMPT

echo
echo "DONE: read-only Claude MCP diagnostic complete."

if [[ "${literal_fail}" -eq 1 ]]; then
  exit 1
fi
