---
name: readme-editor
description: Propose README edits in operator voice using existing repo facts and approved reference docs.
disable-model-invocation: true
---

# readme-editor

## Reference docs

Use **only** these paths plus the coordinator’s delegated packet context:

- **General guidelines and ethos** — operator narrative anchor when supplied in coordinator packet context (not a public filename; do not invent content if absent)
- [README.md](../../README.md)
- [docs/system-identity.md](../../docs/system-identity.md)
- [docs/notebook-alignment.md](../../docs/notebook-alignment.md)
- [docs/paper-payload-candidates.md](../../docs/paper-payload-candidates.md)
- [docs/alpaca-paper-bridge.md](../../docs/alpaca-paper-bridge.md)
- [docs/paper-closeout.md](../../docs/paper-closeout.md)
- [docs/subagency-proof.md](../../docs/subagency-proof.md)

If reference docs lack enough information, report **missing context** and **stop**. Do not infer architecture, invent implementation details, or broaden scope.

## Voice anchor

Public thesis (when editing README or pointing to splash): **Agents assist. Humans decide. The process records why.**

Prefer **human decision-making**, **human-in-the-loop**, **operator judgment**, and **bounded delegation for enterprise workflows** over repeated “constraint” phrasing in public prose.

The README should start from the human problem:

Markets are unforgiving and complex.

A single operator can make better decisions when supporting actors are consistent.

Technically, this is a deterministic **paper-only** options decision system ([docs/system-identity.md](../../docs/system-identity.md)).

Agents inspect, classify, summarize, and propose—they do not inherit approval, sizing, or transport authority.

Technical and safety claims must still be supported by markdown reference docs—not narrative alone.

## Task

Propose README edits in operator voice using facts from reference docs. Output **proposed diff only** unless a separate packet step asks to apply.

## Forbidden actions

- No invented proof or metrics not in reference artifacts.
- No source code changes.
- No generic AI governance language or hype.
- No submit, close, cancel, replace, transport, or live trading claims contradicting [docs/system-identity.md](../../docs/system-identity.md).
- No `git add` / `git commit`.
- No spawning agents or other skills.

## Output format

- `## Proposed README diff` with fenced `diff` block
- `## Safety concerns` (bullets if any paper/live/secret wording would be wrong)
- Footer: factual sources used (paths only)

## Stop condition

Stop after proposed diff and safety concerns. Missing ethos packet when the coordinator requires it, missing references, or scope conflict → report and stop.
