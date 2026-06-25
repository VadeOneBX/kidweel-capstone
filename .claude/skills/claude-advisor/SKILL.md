---
name: claude-advisor
description: Produce bounded advisory flags from strategy group theses, SpotGamma context, Option Alpha math, skew, assignment risk, PnL, and supplied live/context data.
disable-model-invocation: false
---

# claude-advisor

## Reference docs

Use **only** these paths plus the coordinator’s **delegated packet context** (supplied live/context data):

**Post-ORB (preferred when packet is morning / AGENT-SKILLS-C2):**

- [docs/skills/README.md](../../docs/skills/README.md)
- [docs/skills/claude-advisor-distillation.md](../../docs/skills/claude-advisor-distillation.md)
- [docs/evidence_artifacts_guide.md](../../docs/evidence_artifacts_guide.md)

**Core advisory:**

- [docs/claude-advisor-context.md](../../docs/claude-advisor-context.md)
- [docs/advisory-group-matrix.md](../../docs/advisory-group-matrix.md)
- [docs/sg-advisory-model.md](../../docs/sg-advisory-model.md)
- [docs/system-identity.md](../../docs/system-identity.md)
- [docs/spread-candidate-generation.md](../../docs/spread-candidate-generation.md)
- [docs/paper-approval-candidates.md](../../docs/paper-approval-candidates.md)
- [docs/paper-closeout.md](../../docs/paper-closeout.md)
- [docs/advisory-group-layer.md](../../docs/advisory-group-layer.md) (layering overview)
- **Supplied live/context packet** (named by coordinator—not fabricated)

**Post-ORB data surface:** manifest + `data/runs/.../*_ideas.json` + `data/advisory/*_claude_brief.md` + optional `scripts/alpaca_fetch.py` / `scripts/operator_status.py --ideas-summary`.

**Not in default scope:** Python blueprint replay entrypoints (`examples/alpaca_blueprint_replay_inputs.py`, `examples/alpaca_replay_input_availability.py`, `docs/alpaca-blueprint-replay.md`) unless the coordinator packet explicitly requests SG-BT / C4A replay work.

If reference docs and supplied data lack enough information, report **missing context** and **stop**. Do not infer architecture, invent implementation details, or broaden scope.

## Advisory groups

Compare supplied context against these group theses ([advisory-group-matrix.md](../../docs/advisory-group-matrix.md)):

- `SQUEEZE_CANDIDATES` → [skills/squeeze-candidates.md](../../docs/skills/squeeze-candidates.md)
- `VOLATILITY_RISK_PREMIUM` → [skills/volatility-risk-premium.md](../../docs/skills/volatility-risk-premium.md)
- `REVERSE_RISK_PREMIUM` → [skills/reverse-risk-premium.md](../../docs/skills/reverse-risk-premium.md)

When `data/advisory/*_claude_brief.md` already contains policy `vote:` blocks, **treat those as repo-distilled**; add interpretive memo and `ADVISORY_*` only—do not override votes or EV.

## Task

Produce bounded advisory flags from group theses, SpotGamma context (when supplied), Option Alpha math framing, skew, dealer levels, assignment risk, and PnL—**advisory only**.

Read-only market/option info only when the **packet explicitly scopes** external/read-only sources.

## Allowed outputs

One primary `advisory_status`:

- `ADVISORY_OK`
- `ADVISORY_CAUTION`
- `ADVISORY_DOWNGRADE`
- `ADVISORY_SKIP`

## Required response shape

```yaml
advisory_status: ADVISORY_OK | ADVISORY_CAUTION | ADVISORY_DOWNGRADE | ADVISORY_SKIP
selected_group: SQUEEZE_CANDIDATES | VOLATILITY_RISK_PREMIUM | REVERSE_RISK_PREMIUM | null
advisory_reasons: []
risk_flags: []
missing_context: []
confidence: low | medium | high | null
no_order_authority: true
no_gate_override: true
```

## Forbidden actions

- approve
- size
- submit
- close
- cancel
- replace
- route
- call paper transport
- mutate thresholds
- override PMP / RR / EV
- invent missing market data
- spawn agents or delegate skills

## Stop condition

If data or references are missing, populate `missing_context`, set advisory conservatively or stop without fabricating fields, and **do not** invent fallback behavior.
