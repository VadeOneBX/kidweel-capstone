#!/usr/bin/env bash
set -euo pipefail

CREATE_PR=0
if [[ "${1:-}" == "--create-pr" ]]; then
  CREATE_PR=1
fi

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "${ROOT}"

echo "== Kidweel GitHub branch reconciliation audit =="
echo "repo_root=${ROOT}"
echo "branch=$(git branch --show-current)"

echo
echo "1) Fetch remotes"
if ! git fetch --all --prune; then
  echo "WARN: git fetch failed; continuing with local refs only"
fi

echo
echo "2) Local branches and upstreams"
git branch -vv

echo
echo "3) Recent branch activity (top 40)"
git for-each-ref --sort=-committerdate refs/heads refs/remotes \
  --format='%(committerdate:iso8601) %(refname:short) %(subject)' | head -40

current_branch="$(git branch --show-current)"
main_ref="origin/main"
if ! git rev-parse --verify "${main_ref}" >/dev/null 2>&1; then
  echo "WARN: ${main_ref} not found after fetch"
  main_ref="main"
fi

echo
echo "4) Branches to compare against ${main_ref}"
branches_to_check=("${current_branch}")

while IFS= read -r ref; do
  [[ -z "${ref}" ]] && continue
  short="${ref#refs/remotes/}"
  [[ "${short}" == "origin/HEAD" ]] && continue
  [[ "${short}" == "origin/main" ]] && continue
  branches_to_check+=("${short}")
done < <(git for-each-ref --sort=-committerdate --format='%(refname)' refs/remotes/origin 2>/dev/null | head -20)

unique_branches=()
for b in "${branches_to_check[@]}"; do
  seen=0
  for u in "${unique_branches[@]:-}"; do
    if [[ "${u}" == "${b}" ]]; then
      seen=1
      break
    fi
  done
  if [[ "${seen}" -eq 0 ]]; then
    unique_branches+=("${b}")
  fi
done

for branch in "${unique_branches[@]}"; do
  if [[ "${branch}" == origin/* ]]; then
    rev="${branch}"
  elif git show-ref --verify --quiet "refs/remotes/origin/${branch}"; then
    rev="origin/${branch}"
  else
    rev="${branch}"
  fi
  if ! git merge-base --is-ancestor "${main_ref}" "${rev}" 2>/dev/null; then
    echo
    echo "--- branch:${branch} (ref:${rev}) ---"
    echo "commits_not_in_${main_ref}:"
    git log --oneline "${main_ref}..${rev}" 2>/dev/null | head -30 || echo "(none or unreachable)"
    echo "files_changed:"
    git diff --name-status "${main_ref}...${rev}" 2>/dev/null | head -80 || echo "(diff unavailable)"
  else
    echo
    echo "--- branch:${branch} ---"
    echo "status:merged_or_no_unique_commits_vs_${main_ref}"
    ahead_count="$(git rev-list --count "${main_ref}..${rev}" 2>/dev/null || echo 0)"
    echo "commits_ahead_of_${main_ref}:${ahead_count}"
    if [[ "${ahead_count}" != "0" ]]; then
      git log --oneline "${main_ref}..${rev}" | head -20
      git diff --name-status "${main_ref}...${rev}" | head -80
    fi
  fi
done

echo
echo "5) gh authentication"
if command -v gh >/dev/null 2>&1; then
  if gh auth status 2>&1; then
  gh_ok=1
  else
    gh_ok=0
    echo "gh_auth:not_active"
  fi
else
  gh_ok=0
  echo "missing:gh"
fi

pr_title="Reconcile Claude Code MCP tooling and branch work"
pr_body_file="$(mktemp)"
{
  echo "## Summary"
  echo "- MCP-C1D: Claude Doctor / global vs project settings diagnostic tooling"
  echo "- Branch reconciliation audit toward \`main\` via PR (no direct merge)"
  echo ""
  echo "## Diagnostic"
  echo "Run \`bash scripts/diagnose_claude_doctor_env.sh\` before merge; fix malformed \`~/.claude/settings.json\` if reported."
  echo ""
  echo "## Changed files (current branch vs ${main_ref})"
  git diff --name-status "${main_ref}...HEAD" 2>/dev/null || true
  echo ""
  echo "## Tests"
  echo "\`PYTHONPATH=src python -m pytest tests -q\` (operator-run)"
  echo ""
  echo "## Trading posture"
  echo "Paper-only; no live-trading posture changes; no execution/gate/schema/transport changes in this tooling pack."
} >"${pr_body_file}"

echo
echo "6) PR command (manual)"
echo "gh pr create --base main --head ${current_branch} --title \"${pr_title}\" --body-file <(see template below)"
echo "--- PR body template ---"
cat "${pr_body_file}"
echo "--- end template ---"

if [[ "${CREATE_PR}" -eq 1 ]]; then
  if [[ "${gh_ok}" -ne 1 ]]; then
    echo "ERROR: --create-pr requested but gh is not authenticated" >&2
    rm -f "${pr_body_file}"
    exit 1
  fi
  echo
  echo "Creating PR (no force push, no merge, no branch delete)..."
  gh pr create --base main --head "${current_branch}" \
    --title "${pr_title}" \
    --body-file "${pr_body_file}"
fi

rm -f "${pr_body_file}"
echo
echo "DONE: branch reconciliation audit complete."
