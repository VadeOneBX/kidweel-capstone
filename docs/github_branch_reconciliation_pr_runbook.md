# GitHub branch reconciliation PR runbook

Audit branch drift against `origin/main` and open a PR into `main` without force push, direct merge, or branch deletion.

## Scope

- Git and `gh` tooling only
- No changes to execution logic, gates, schemas, transport, or Alpaca submit/cancel/replace paths
- No live-trading posture changes

## Files

- `scripts/audit_branch_reconciliation.sh`
- `docs/github_branch_reconciliation_pr_runbook.md`

## Operator sequence (repo root)

```bash
bash scripts/audit_branch_reconciliation.sh
```

Review commits and file lists vs `origin/main`. When the audit looks sane and tests pass:

```bash
PYTHONPATH=src python -m pytest tests -q
bash scripts/audit_branch_reconciliation.sh --create-pr
```

Requires `gh auth status` to be active. The script does **not** merge to `main`.

## What the audit script does

1. Resolves repo root and prints current branch.
2. `git fetch --all --prune`
3. `git branch -vv`
4. Recent branch activity (40 refs)
5. Compares current and recent remote branches to `origin/main`:
   - `git log --oneline origin/main..BRANCH`
   - `git diff --name-status origin/main...BRANCH`
6. `gh auth status`
7. Prints suggested `gh pr create` command and body template.
8. With `--create-pr`: creates PR titled **Reconcile Claude Code MCP tooling and branch work** (body includes diagnostic note, changed files, tests reminder, paper-only statement).

## Guardrails

- Never `--force` push
- Never delete branches
- Never merge directly to `main` from this script

## Related

- [mcp_c1d_claude_doctor_env_diagnostic.md](mcp_c1d_claude_doctor_env_diagnostic.md)
