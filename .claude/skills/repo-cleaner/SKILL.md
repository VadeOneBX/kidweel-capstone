---
name: repo-cleaner
description: Classify repo paths as files, helpers, tests, or docs. Use only when the coordinator explicitly invokes repo-cleaner. Output a classification table; no edits unless separately asked.
disable-model-invocation: true
---

# repo-cleaner

**Reference docs:** [docs/subagent-governance.md](../../docs/subagent-governance.md), [docs/subagency-proof.md](../../docs/subagency-proof.md), [.cursor/rules/capstone-repo.mdc](../../.cursor/rules/capstone-repo.mdc)

## Purpose

Classify repository paths (or a coordinator-supplied list) into: **source**, **helpers/utilities**, **tests**, **docs**, **config**, **other**. Support bounded review—not refactoring.

## Instructions

1. Read only paths the coordinator scopes (or top-level inventory if scope says “repo root summary”).
2. Build a **classification table** with columns: `path`, `category`, `notes` (one line).
3. Do **not** edit files unless the coordinator explicitly asks in a **separate** follow-up—not in the same invocation.
4. Do **not** change source code in this skill’s default mode.
5. Do **not** run `git add`, `git commit`, or any submit/transport command.
6. Do **not** spawn subagents or invoke other skills.
7. **Stop after** delivering the classification table. If scope or references are missing, report the blocker and stop.

## Output format

```markdown
## Classification

| path | category | notes |
|------|----------|-------|
| ... | tests | ... |
```
