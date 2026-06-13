---
name: repo-cleaner
description: Classify repository helpers, tests, docs, and scripts into canonical, legacy, experimental, archive, or delete-candidate groups.
disable-model-invocation: true
---

# repo-cleaner

## Reference docs

Use **only** these paths plus the coordinator’s delegated packet context:

- [README.md](../../README.md)
- [docs/notebook-alignment.md](../../docs/notebook-alignment.md)
- [docs/system-identity.md](../../docs/system-identity.md)
- [docs/alpaca-paper-bridge.md](../../docs/alpaca-paper-bridge.md)
- [docs/paper-closeout.md](../../docs/paper-closeout.md)

If reference docs lack enough information, report **missing context** and **stop**. Do not infer architecture, invent implementation details, or broaden scope.

## Task

Classify repository helpers, tests, docs, and scripts (coordinator-scoped paths) into groups:

- canonical
- legacy
- experimental
- archive
- delete-candidate

When using the **repo-cleaner agent** manifest, also allow label **safety-critical** for paths tied to paper transport, credentials, or gates (classification only—no edits).

## Forbidden actions

- No edits unless a **separate** packet explicitly asks.
- No source code changes in default mode.
- No `git add` / `git commit`.
- No submit, close, cancel, replace, or transport commands.
- No spawning agents or other skills.

## Output format

```markdown
## Classification

| path | group | notes |
|------|-------|-------|
```

## Stop condition

Deliver the table and **stop**. Missing reference file, unclear scope, or edit request without packet → report blocker and stop.
