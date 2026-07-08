---
name: public-language-auditor
description: Audit public-facing Kidweel copy for HITL emphasis, authority safety, and non-generic language before README, splash, or docs changes ship.
disable-model-invocation: true
---

# public-language-auditor

## Reference docs

Use **only** these paths plus the coordinator’s delegated packet context:

- [README.md](../../README.md)
- [docs/subagency-proof.md](../../docs/subagency-proof.md)
- [docs/public_readiness.md](../../docs/public_readiness.md)
- [kidweel-site/index.html](../../kidweel-site/index.html)
- [docs/system-identity.md](../../docs/system-identity.md)
- [docs/alpaca-paper-bridge.md](../../docs/alpaca-paper-bridge.md)
- [docs/paper-closeout.md](../../docs/paper-closeout.md)

If reference docs lack enough information, report **missing context** and **stop**. Do not infer architecture, invent implementation details, or broaden scope.

## Purpose

Audit public-facing Kidweel language (supplied copy or scoped paths) for:

- originality
- human-in-the-loop emphasis
- authority safety
- mobile readability
- enterprise seriousness
- non-generic AI language

## Rules

### 1. Preferred language

Use:

- Agents assist. Humans decide. The process records why.
- human decision-making
- human-in-the-loop
- bounded delegation for enterprise workflows
- operator judgment
- review before action
- audit trail records the path
- useful delegation without inherited authority

### 2. Allowed but limited language

Use sparingly:

- constraint-first
- built under constraint
- adaptable under constraint

These should be visual/map labels, not repeated prose anchors.

### 3. Avoid language

Flag:

- agentic workflows
- AI-powered productivity
- autonomous agents
- unlock / unleash
- next-generation AI
- generic tool orchestration
- can enable live trade
- live trading
- signal service
- investment advice
- execution authority
- inherited authority

### 4. Safety boundaries

Public language must not imply:

- autonomous trading
- live-money execution
- order submission authority
- gate mutation by agents
- paper validation as investment performance
- advice or signal service

### 5. Example discipline

Flag any public example list over **3 bullets** unless it is a technical reference map (e.g. skill reference tables).

## Forbidden actions

- No direct repo edits, commits, or file writes.
- No submit, close, cancel, replace, transport, or live trading claims contradicting reference docs.
- No spawning agents or other skills.

## Output format

Return:

```markdown
## Public Language Audit

| Area | Status | Finding | Fix |
|------|--------|---------|-----|
| Originality | PASS/WATCH/FAIL | ... | ... |
| HITL emphasis | PASS/WATCH/FAIL | ... | ... |
| Authority safety | PASS/WATCH/FAIL | ... | ... |
| Mobile readability | PASS/WATCH/FAIL | ... | ... |
| Enterprise seriousness | PASS/WATCH/FAIL | ... | ... |

## Problem phrases

List exact phrases and why they fail.

## Replacement copy

Provide final copy blocks only.
```

## Stop condition

If a required reference doc is missing from the workspace, report:

`MISSING_CONTEXT: <file>`

and **stop**. Do not substitute other sources.

Stop after audit table, problem phrases, and replacement copy. Scope conflict or request to apply edits directly → report and stop.
