# Advisory group layer

Interpretive advisory above deterministic gates—**no execution authority**. Spread math, approval, and transport stay repo-owned.

**Advisory proposes; the system decides; operator/HITL controls transport.**

**Advisory** means claude-advisor and advisory agents. Claude.ai desktop is an operator-facing review surface and future allowlisted command-trigger surface; Claude mobile is visibility/review only. Claude Code / Cursor Claude and Cursor mobile are implementation/review surfaces—not runtime authority. None of these surfaces approve, size, submit, transport, bypass gates, or run arbitrary shell.

## Layers

| Layer | Owner | Output |
|-------|--------|--------|
| Tier 3 idea skills | Subagents (packet-scoped) | `data/runs/<date>/<run_id>_<agent>_ideas.json` |
| Idea distillation | `qops.advisory.idea_distillation` | Policy `vote:` blocks in `claude_brief` |
| claude-advisor skill | Coordinator invocation | `ADVISORY_*` + memo from **supplied** artifacts |

## Related

- [docs/skills/README.md](./skills/README.md) (AGENT-SKILLS-C2 index)
- [advisory-group-matrix.md](./advisory-group-matrix.md)
- [claude-advisor-context.md](./claude-advisor-context.md)
- [.claude/skills/claude-advisor/SKILL.md](../.claude/skills/claude-advisor/SKILL.md)
