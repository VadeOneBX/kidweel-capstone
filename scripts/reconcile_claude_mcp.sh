#!/usr/bin/env bash
set -euo pipefail

repo_root="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1
  pwd
)"

echo "Repo root: ${repo_root}"

if command -v claude >/dev/null 2>&1; then
  echo "claude command: present"
  has_claude=1
else
  echo "claude command: missing"
  has_claude=0
fi

for required in "CLAUDE.md" "AGENTS.md"; do
  if [[ -f "${repo_root}/${required}" ]]; then
    echo "${required}: present"
  else
    echo "${required}: missing"
  fi
done

if [[ -d "${repo_root}/.claude/agents" ]]; then
  echo ".claude/agents: present"
else
  echo ".claude/agents: missing"
fi

if [[ -f "${repo_root}/.claude/settings.json" ]]; then
  echo ".claude/settings.json: present (will be overwritten)"
else
  echo ".claude/settings.json: missing (will be created)"
fi

cursor_mcp="${repo_root}/.cursor/mcp.json"
claude_settings="${repo_root}/.claude/settings.json"

if [[ ! -f "${cursor_mcp}" ]]; then
  echo "ERROR: required file missing: ${cursor_mcp}" >&2
  exit 1
fi

mkdir -p "${repo_root}/.claude"
cp "${cursor_mcp}" "${claude_settings}"
echo "Copied .cursor/mcp.json -> .claude/settings.json"

if rg -n --fixed-strings --ignore-case \
  -e '"apiKey"' \
  -e '"secretKey"' \
  -e 'ALPACA_PAPER_API_KEY' \
  -e 'ALPACA_PAPER_SECRET_KEY' \
  -e 'AKIA' \
  "${claude_settings}" >/dev/null; then
  echo "ERROR: inline credential-like content detected in .claude/settings.json" >&2
  exit 1
fi
echo "Inline credential scan: clean"

if [[ "${has_claude}" -eq 1 ]]; then
  echo "Running: claude /doctor"
  if ! claude /doctor; then
    echo "claude /doctor returned non-zero; inspect output above."
  fi
else
  echo "Skipped: claude /doctor (claude command missing)"
fi

cat <<'EOF'
Claude Code manual smoke-test:
  /status
  /agents
  /mcp
  safety-auditor review of CLAUDE.md, AGENTS.md, and .claude/settings.json
EOF
