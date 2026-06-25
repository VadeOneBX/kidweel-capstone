# MCP-C1B Alpaca QA and Claude shadow repo deprecation

This packet adds a reusable QA script for paper-only Alpaca checks and formalizes Claude shadow-repo deprecation as an authority source.

## Scope

- Repo tooling and docs only
- No changes to execution logic, gates, schemas, or transport behavior
- No live-trading posture change

## Files

- `scripts/full_alpaca_qa.sh`
- `docs/mcp_c1b_alpaca_qa_shadow_deprecation.md`
- `docs/deprecated/claude_shadow_repo.md`

## Operator run (repo root)

```bash
bash scripts/full_alpaca_qa.sh
```

## What the script does

1. Fails if `ALPACA_LIVE_TRADE=true` or `ALPACA_LIVE_TRADE=1`.
2. Checks presence of paper credential environment variables.
3. If Alpaca CLI exists, runs:
   - `alpaca profile show --quiet`
   - `alpaca account get --quiet`
4. Scans `.cursor/mcp.json` and `.claude/settings.json` for inline credential-like content and fails if found.
5. Runs:
   - `PYTHONPATH=src python -m pytest tests -q`
6. Confirms `docs/deprecated/claude_shadow_repo.md` exists.
7. Warns on nearby likely shadow-repo directories; does not delete anything.

## Verification notes

- Script is runnable from repo root via `bash`.
- Script keeps the repo in paper-only QA posture.
- Script is intentionally read/verify oriented and non-destructive.
