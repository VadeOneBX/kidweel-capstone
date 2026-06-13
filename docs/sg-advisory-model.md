# SpotGamma advisory model

**Status:** TODO — stub for CLAUDE-FOOTING-C1 / claude-advisor skill.

## Intended role

Describe how **SpotGamma-oriented context** (walls, gamma, skew summaries) feeds **advisory flags only**—not payloads, gates, or transport.

Advisory may use supplied replay/enrichment artifacts when the coordinator attaches them. Missing data → report in `missing_context`; do not invent levels.

## Related

- [advisory-group-layer.md](./advisory-group-layer.md)
- [advisory-group-matrix.md](./advisory-group-matrix.md)
- [claude-advisor-context.md](./claude-advisor-context.md)
- Ingestion docs: [spotgamma-to-replay.md](./spotgamma-to-replay.md) (context only; do not expand scope here)

## TODO

- Document allowed advisory inputs vs forbidden re-derivation (`regime_label`, `confidence`, `gamma_ratio`)
- Align with [system-identity.md](./system-identity.md) ML/subagent policy
