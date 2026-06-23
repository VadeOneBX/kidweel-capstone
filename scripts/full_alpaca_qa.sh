#!/usr/bin/env bash
set -euo pipefail

repo_root="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1
  pwd
)"

echo "Repo root: ${repo_root}"

live_trade_value="${ALPACA_LIVE_TRADE:-}"
if [[ "${live_trade_value}" == "true" || "${live_trade_value}" == "1" ]]; then
  echo "ERROR: ALPACA_LIVE_TRADE must not be true/1 for paper QA." >&2
  exit 1
fi
echo "ALPACA_LIVE_TRADE guard: safe (${live_trade_value:-unset})"

paper_api_key="${ALPACA_PAPER_API_KEY:-}"
paper_secret_key="${ALPACA_PAPER_SECRET_KEY:-}"
paper_base_url="${ALPACA_PAPER_BASE_URL:-}"

if [[ -n "${paper_api_key}" ]]; then
  echo "ALPACA_PAPER_API_KEY: present"
else
  echo "ALPACA_PAPER_API_KEY: missing"
fi

if [[ -n "${paper_secret_key}" ]]; then
  echo "ALPACA_PAPER_SECRET_KEY: present"
else
  echo "ALPACA_PAPER_SECRET_KEY: missing"
fi

if [[ -n "${paper_base_url}" ]]; then
  echo "ALPACA_PAPER_BASE_URL: present (${paper_base_url})"
else
  echo "ALPACA_PAPER_BASE_URL: missing"
fi

if command -v alpaca >/dev/null 2>&1; then
  echo "alpaca CLI: present; running profile/account checks"
  if ! alpaca profile show --quiet; then
    echo "WARN: alpaca profile show --quiet failed" >&2
  fi
  if ! alpaca account get --quiet; then
    echo "WARN: alpaca account get --quiet failed" >&2
  fi
else
  echo "alpaca CLI: missing; skipping CLI checks"
fi

for cfg in "${repo_root}/.cursor/mcp.json" "${repo_root}/.claude/settings.json"; do
  if [[ -f "${cfg}" ]]; then
    if rg -n --fixed-strings --ignore-case \
      -e '"apiKey"' \
      -e '"secretKey"' \
      -e 'ALPACA_PAPER_API_KEY' \
      -e 'ALPACA_PAPER_SECRET_KEY' \
      -e 'AKIA' \
      "${cfg}" >/dev/null; then
      echo "ERROR: inline credential-like content detected in ${cfg}" >&2
      exit 1
    fi
    echo "Inline credential scan clean: ${cfg}"
  else
    echo "WARN: config missing for credential scan: ${cfg}"
  fi
done

echo "Running test suite: PYTHONPATH=src python -m pytest tests -q"
(
  cd "${repo_root}"
  PYTHONPATH=src python -m pytest tests -q
)

deprecation_doc="${repo_root}/docs/deprecated/claude_shadow_repo.md"
if [[ -f "${deprecation_doc}" ]]; then
  echo "Deprecation doc present: ${deprecation_doc}"
else
  echo "ERROR: expected deprecation doc missing: ${deprecation_doc}" >&2
  exit 1
fi

echo "Scanning for nearby possible shadow repo directories (warning only)"
for maybe in "${repo_root}/../kidweel-claude" "${repo_root}/../claude_shadow_repo" "${repo_root}/../kidweel-capstone-claude"; do
  if [[ -d "${maybe}" ]]; then
    echo "WARN: possible shadow repo dir detected: ${maybe}"
  fi
done

echo "full_alpaca_qa.sh completed"
