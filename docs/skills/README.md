# Post-ORB advisory skills (AGENT-SKILLS-C2)

Tier 3 agents emit typed ideas; deterministic distillation writes policy votes into the morning brief. **Not approval, not transport.**

| Skill doc | Agent id |
|-----------|----------|
| [squeeze-candidates.md](./squeeze-candidates.md) | `squeeze-candidates` |
| [volatility-risk-premium.md](./volatility-risk-premium.md) | `volatility-risk-premium` |
| [reverse-risk-premium.md](./reverse-risk-premium.md) | `reverse-risk-premium` |
| [claude-advisor-distillation.md](./claude-advisor-distillation.md) | `claude-advisor` (interpret votes only) |
| [alpaca-cli-skills.md](./alpaca-cli-skills.md) | Operator read-only CLIs |

**Context source (not a repo file named `sg-context.md`):** manifest `context_artifact` (processed SpotGamma / feature rows). Coordinator may attach a human-readable memo; cite its path in each idea’s `source` field.

**Morning entrypoint:** `scripts/orb_morning_loop.py`. **Not** `examples/alpaca_blueprint_*.py` unless the packet is SG-BT replay.
