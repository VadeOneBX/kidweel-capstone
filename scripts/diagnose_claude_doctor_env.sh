#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "${ROOT}"

GLOBAL_SETTINGS="${HOME}/.claude/settings.json"
PROJECT_SETTINGS="${ROOT}/.claude/settings.json"
GLOBAL_CURSOR="${HOME}/.cursor/mcp.json"
PROJECT_CURSOR="${ROOT}/.cursor/mcp.json"

runtime_missing=0
global_json_ok=0
global_json_malformed=0
project_json_ok=0
project_json_missing=0
project_json_malformed=0
inline_secret_any=0
paper_key_missing=0
paper_secret_missing=0
global_server_names=""
project_server_names=""

echo "== Kidweel Claude Doctor MCP environment diagnostic (MCP-C1D) =="
echo "repo_root=${ROOT}"

echo
echo "0) Git context"
echo "branch=$(git branch --show-current 2>/dev/null || echo unknown)"
if [[ -z "$(git status --porcelain 2>/dev/null)" ]]; then
  echo "working_tree:clean"
else
  echo "working_tree:dirty"
  git status --short
fi

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
echo "2) Runtime commands"
for c in uv uvx python3 git; do
  if command -v "${c}" >/dev/null 2>&1; then
    echo "found:${c}=$(command -v "${c}")"
  else
    echo "missing:${c}"
    runtime_missing=1
  fi
done
for c in gh; do
  if command -v "${c}" >/dev/null 2>&1; then
    echo "found:${c}=$(command -v "${c}")"
  else
    echo "missing:${c} (optional for this script)"
  fi
done
if [[ -x "${ROOT}/.venv/bin/python" ]]; then
  echo "found:.venv/bin/python=${ROOT}/.venv/bin/python"
  "${ROOT}/.venv/bin/python" --version 2>/dev/null || true
else
  echo "missing:.venv/bin/python"
fi

echo
echo "3) JSON config files (read-only)"
config_paths=(
  "${GLOBAL_SETTINGS}"
  "${PROJECT_SETTINGS}"
  "${GLOBAL_CURSOR}"
  "${PROJECT_CURSOR}"
)

analyze_json() {
  local label="$1"
  local path="$2"
  python3 - "${label}" "${path}" <<'PY'
import json
import re
import sys
from pathlib import Path

label, path_s = sys.argv[1], sys.argv[2]
path = Path(path_s)
print(f"file:{label}")
print(f"path:{path}")

if not path.is_file():
    print("status:MISSING")
    print("json:SKIP")
    sys.exit(0)

raw = path.read_text()
try:
    data = json.loads(raw)
except json.JSONDecodeError as e:
    print("json:MALFORMED_JSON")
    print(f"json_error:{e}")
    sys.exit(0)

print("json:VALID_JSON")
servers = data.get("mcpServers") or data.get("mcp_servers") or {}
if not servers:
    print("mcp_servers:none")
    sys.exit(0)

ref_pat = re.compile(r"^\$\{[^}]+\}$")
literal_secret = 0

def classify_env(key: str, value) -> str:
    global literal_secret
    if not isinstance(value, str):
        return "NONSTRING_REDACTED"
    if ref_pat.match(value):
        return f"REFERENCE:{value}"
    ku = key.upper()
    if "SECRET" in ku or "PASSWORD" in ku or "TOKEN" in ku:
        if value.strip():
            literal_secret = 1
            return "LITERAL_SECRET_DETECTED"
        return "NON_SECRET_LITERAL"
    if ("KEY" in ku or "API" in ku) and (
        value.startswith("PK")
        or value.startswith("AKIA")
        or value.startswith("sk-")
        or (len(value) >= 16 and value.isalnum())
    ):
        literal_secret = 1
        return "LITERAL_SECRET_DETECTED"
    return "NON_SECRET_LITERAL"

names = []
for name, cfg in servers.items():
    names.append(name)
    print(f"server:{name}")
    print(f"  command:{cfg.get('command')}")
    print(f"  args:{cfg.get('args')}")
    env = cfg.get("env") or {}
    if not env:
        print("  env:none")
        continue
    for k in sorted(env.keys()):
        print(f"  env:{k}={classify_env(k, env[k])}")

print("server_names:" + ",".join(names))
if literal_secret:
    print("inline_secret:yes")
else:
    print("inline_secret:no")
PY
}

for p in "${config_paths[@]}"; do
  case "${p}" in
    "${GLOBAL_SETTINGS}") label="global_claude_settings" ;;
    "${PROJECT_SETTINGS}") label="project_claude_settings" ;;
    "${GLOBAL_CURSOR}") label="global_cursor_mcp" ;;
    "${PROJECT_CURSOR}") label="project_cursor_mcp" ;;
    *) label="unknown" ;;
  esac
  echo "---"
  out="$(analyze_json "${label}" "${p}")"
  echo "${out}"
  if echo "${out}" | grep -q 'json:MALFORMED_JSON'; then
    if [[ "${label}" == "global_claude_settings" ]]; then
      global_json_malformed=1
    fi
    if [[ "${label}" == "project_claude_settings" ]]; then
      project_json_malformed=1
    fi
  fi
  if echo "${out}" | grep -q 'json:VALID_JSON'; then
    if [[ "${label}" == "global_claude_settings" ]]; then
      global_json_ok=1
    fi
    if [[ "${label}" == "project_claude_settings" ]]; then
      project_json_ok=1
    fi
  fi
  if echo "${out}" | grep -q 'status:MISSING'; then
    if [[ "${label}" == "project_claude_settings" ]]; then
      project_json_missing=1
    fi
  fi
  if echo "${out}" | grep -q 'inline_secret:yes'; then
    inline_secret_any=1
  fi
  sn="$(echo "${out}" | sed -n 's/^server_names://p' | head -1)"
  if [[ -n "${sn}" ]]; then
    if [[ "${label}" == "global_claude_settings" ]]; then
      global_server_names="${sn}"
    fi
    if [[ "${label}" == "project_claude_settings" ]]; then
      project_server_names="${sn}"
    fi
  fi
done

echo
echo "4) Claude settings precedence"
if [[ "${global_json_malformed}" -eq 1 ]]; then
  echo "risk:GLOBAL_MALFORMED_BLOCKER"
elif [[ "${global_json_ok}" -eq 1 ]]; then
  echo "risk:global_settings_valid"
fi

if [[ "${project_json_missing}" -eq 1 ]]; then
  echo "risk:project_settings_missing"
elif [[ "${project_json_malformed}" -eq 1 ]]; then
  echo "risk:project_settings_malformed"
elif [[ "${project_json_ok}" -eq 1 ]]; then
  echo "risk:PROJECT_VALID"
fi

if [[ -n "${global_server_names}" && -n "${project_server_names}" ]]; then
  IFS=',' read -r -a g_arr <<<"${global_server_names}"
  IFS=',' read -r -a p_arr <<<"${project_server_names}"
  for g in "${g_arr[@]}"; do
    for pr in "${p_arr[@]}"; do
      if [[ "${g}" == "${pr}" ]]; then
        echo "risk:DUPLICATE_SERVER_WARNING:${g}"
      fi
    done
  done
fi

if [[ "${inline_secret_any}" -eq 1 ]]; then
  echo "risk:inline_secret_literals_detected"
fi

echo
echo "5) Same-shell env presence (names only)"
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
    [[ "${k}" == "ALPACA_PAPER_KEY" ]] && paper_key_missing=1
    [[ "${k}" == "ALPACA_PAPER_SECRET" ]] && paper_secret_missing=1
  fi
done
if [[ "${paper_key_missing}" -eq 1 && "${paper_secret_missing}" -eq 1 ]]; then
  echo "risk:paper_env_missing_in_launch_shell"
fi

echo
echo "6) uvx read-only availability"
if command -v uvx >/dev/null 2>&1; then
  uvx --help >/dev/null 2>&1 && echo "uvx_help:ok" || echo "uvx_help:failed"
else
  echo "uvx_help:skipped_missing_uvx"
fi

echo
echo "7) Manual operator test"
cat <<'PROMPT'
source .venv/bin/activate
# load paper env vars in the same shell (never paste secrets into chat)
bash scripts/diagnose_claude_doctor_env.sh
claude

Inside Claude Code:
/doctor
/status
/agents
/mcp

If /doctor reports malformed ~/.claude/settings.json, fix or remove invalid JSON there first.
Malformed global settings are skipped entirely by Claude Code.
PROMPT

echo
echo "DONE: read-only Claude Doctor MCP environment diagnostic complete."

final_exit=0
if [[ "${inline_secret_any}" -eq 1 ]]; then
  final_exit=5
elif [[ "${global_json_malformed}" -eq 1 ]]; then
  final_exit=3
elif [[ "${project_json_missing}" -eq 1 || "${project_json_malformed}" -eq 1 ]]; then
  final_exit=4
elif [[ "${runtime_missing}" -eq 1 ]]; then
  final_exit=6
elif [[ "${paper_key_missing}" -eq 1 && "${paper_secret_missing}" -eq 1 ]]; then
  final_exit=7
fi

echo "exit_code:${final_exit}"
exit "${final_exit}"
