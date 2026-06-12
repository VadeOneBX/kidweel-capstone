---
name: readme-editor
description: Propose README rewrites in operator voice from existing repo facts. Use only when the coordinator explicitly invokes readme-editor. Output proposed diff only; no file writes.
disable-model-invocation: true
---

# readme-editor

**Reference docs:** [docs/subagent-governance.md](../../docs/subagent-governance.md), [docs/subagency-proof.md](../../docs/subagency-proof.md), [docs/system-identity.md](../../docs/system-identity.md), [docs/c13-governance.md](../../docs/c13-governance.md), [README.md](../../README.md)

## Purpose

Rewrite or refine README sections in **operator voice** using facts already in the repo (README, `docs/`, code comments where cited). Improve clarity and navigation—not marketing.

## Instructions

1. Read [README.md](../../README.md) and cited docs; do not invent capabilities, metrics, or “proof” not present in repo artifacts.
2. Output a **proposed diff only** (unified diff or before/after blocks)—do not write files unless the coordinator explicitly requests apply in a separate step.
3. No hype, AI-sales language, or autonomous-agent claims contradicting [system-identity.md](../../docs/system-identity.md).
4. No source code changes as part of this skill.
5. No `git add` / `git commit`. No transport or paper commands.
6. Do not spawn subagents.
7. Missing references or unclear scope → report and stop.

## Output format

- Heading: `## Proposed README diff`
- Body: unified diff or before/after blocks in a fenced `diff` block
- Footer: bullet list of factual sources (doc paths only)
