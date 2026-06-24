# Agent map C1a — corrections (compact B)

**Supersedes** [AGENT-MAP-C1_spotgamma_strategy.md](AGENT-MAP-C1_spotgamma_strategy.md) on any conflict. **Packet:** CAPSTONE-FINAL-SPRINT-C1 / ENTERPRISE-WORKFLOW-C1.

---

## B1 — Hydration lanes are not agents

`candidate_loop_status`, `hydration_status`, and expression statuses (`PRIMARY`, `WATCH`, `FAILED_EXPRESSION`) are **deterministic capability lanes** inside `qops.pipeline.alpaca_hydration_loop`. Do not document them as separate autonomous agents. The morning brief section “Hydration loop (capability lanes, not new agents)” is intentional.

---

## B2 — Capstone execution scope

| Topic | C1a rule |
|-------|----------|
| Default transport | Dry-run; paper submit requires explicit operator opt-in (`--submit-paper`) |
| Sprint primary structure | **Bull call spread** multi-leg paper only |
| Credit / iron condor / live | Out of scope for this sprint |
| Cheap underlyings (NIO, BB, etc.) | Screening candidates only—no guaranteed trades |
| Quantity target | 2 contracts when guards allow; guard reject is valid evidence |

---

## B3 — Claude Code repo access

Claude may audit and advise per [docs/claude_code_access_runbook.md](docs/claude_code_access_runbook.md). Claude may **not** run paper submit scripts, MCP order tools, or live flags. Local rules stay gitignored (`.claude/rules/`, `.claude/settings.json`).

---

## B4 — Accept vs advisory

| Source | Can approve paper transport? |
|--------|------------------------------|
| `risk_audit.csv` `classification` | Mechanical gate outcome only |
| `claude_brief.md` | No |
| `ADVISORY_*` from claude-advisor | No |
| Coordinator + dedicated paper packet | Human approval layer |

A row with `APPROVED_FOR_PAPER_REVIEW` is **not** an order—it is eligibility for a **separate** payload/transport step.

---

## B5 — Swarm prevention (unchanged, reinforced)

- One coordinator; no subagent spawning subagents.
- Same validation path for all delegates ([docs/subagency-proof.md](docs/subagency-proof.md)).
- MCP answers narrow calls; it does not interpret morning briefs into orders.

---

## B6 — Broken doc hygiene

If README or handoffs reference missing artifacts, prefer adding the canonical doc (e.g. [docs/evidence_artifacts_guide.md](docs/evidence_artifacts_guide.md)) over duplicating tables in chat.
