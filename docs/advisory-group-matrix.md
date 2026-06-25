# Advisory group matrix

Maps coordinator-supplied context to **one primary group** for claude-advisor labeling (`selected_group`). Post-ORB idea templates live under [docs/skills/](./skills/). Not approval or sizing.

## Groups

| Group | Idea skill (3 ideas post-ORB) | Thesis (summary) |
|-------|-------------------------------|------------------|
| `SQUEEZE_CANDIDATES` | [skills/squeeze-candidates.md](./skills/squeeze-candidates.md) | Walls, gamma concentration, ORB breach vs. trend |
| `VOLATILITY_RISK_PREMIUM` | [skills/volatility-risk-premium.md](./skills/volatility-risk-premium.md) | VRP richness, skew direction, wall + VRP alignment |
| `REVERSE_RISK_PREMIUM` | [skills/reverse-risk-premium.md](./skills/reverse-risk-premium.md) | Cheap vol, catalyst proximity, implied move vs. debit |

## Distillation (deterministic)

Repo-owned: `qops.advisory.idea_distillation` → policy votes in `data/advisory/<run_id>_claude_brief.md`. See [skills/claude-advisor-distillation.md](./skills/claude-advisor-distillation.md).

Claude-advisor **interprets** votes and may emit `ADVISORY_*`; it does not replace distillation math or gates.

## Related

- [advisory-group-layer.md](./advisory-group-layer.md)
- [sg-advisory-model.md](./sg-advisory-model.md)
- [evidence_artifacts_guide.md](./evidence_artifacts_guide.md)
