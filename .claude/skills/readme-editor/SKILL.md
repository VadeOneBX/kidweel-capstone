---
name: readme-editor
description: Propose README edits in operator voice using existing repo facts and approved reference docs.
disable-model-invocation: true
---

# readme-editor

## Reference docs

Use **only** these paths plus the coordinator’s delegated packet context:

- `June26 Kidweel Survivability.docx` if supplied in packet context (also at repo root: [June26 Kidweel Survivability.docx](../../June26%20Kidweel%20Survivability.docx) when present)
- [README.md](../../README.md)
- [docs/system-identity.md](../../docs/system-identity.md)
- [docs/notebook-alignment.md](../../docs/notebook-alignment.md)
- [docs/paper-payload-candidates.md](../../docs/paper-payload-candidates.md)
- [docs/alpaca-paper-bridge.md](../../docs/alpaca-paper-bridge.md)
- [docs/paper-closeout.md](../../docs/paper-closeout.md)
- [docs/subagency-proof.md](../../docs/subagency-proof.md)

If reference docs lack enough information, report **missing context** and **stop**. Do not infer architecture, invent implementation details, or broaden scope.

## Voice anchor

The README should start from the human problem:

Markets are unforgiving and complex.

A single operator can make better decisions when supporting actors are consistent.

Technically, this is a deterministic paper-live options decision system.

But the point is that agents can help form better questions without being allowed to force the answer.

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

Stop after proposed diff and safety concerns. Missing `.docx` when packet requires it, missing references, or scope conflict → report and stop.
