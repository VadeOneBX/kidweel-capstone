# Claude Advisor context

How the **claude-advisor** repo skill/subagent fits Kidweel: the only **interpretive** project skill in [SUBAGENCY-PROOF-C2](./subagency-proof.md).

**Not the same as:** **Claude.ai desktop** (operator review / future allowlisted commands), **Claude mobile** (review-only unless allowlisted), or **Claude Code / Cursor Claude** (IDE repo edits). Those surfaces do not replace claude-advisor labels or gain approval/transport authority.

**Reference docs for this skill:** [subagency-proof.md — Skill reference map](./subagency-proof.md#skill-reference-map) and [CLAUDE.md](../CLAUDE.md). Post-ORB skills: [skills/README.md](./skills/README.md). Group map: [advisory-group-matrix.md](./advisory-group-matrix.md). SpotGamma inputs: [sg-advisory-model.md](./sg-advisory-model.md).

- `docs/claude-advisor-context.md` (this file)
- `docs/skills/README.md` and `docs/skills/claude-advisor-distillation.md` (when packet is post-ORB / AGENT-SKILLS-C2)
- `docs/system-identity.md`
- `docs/spread-candidate-generation.md`
- `docs/paper-approval-candidates.md`
- `docs/paper-closeout.md`
- `docs/evidence_artifacts_guide.md` (morning artifact paths; post-ORB chain)
- **Supplied live/context data** (coordinator packet only)

The skill may only use these docs plus delegated packet context. Insufficient information → report missing context and stop. Do not infer architecture, invent implementation details, or broaden scope.

---

## Role

**Claude Advisor** is the only interpretive skill in the subagency proof set. The other proof skills classify, propose doc diffs, or audit safety posture without market interpretation.

Claude Advisor may read **live or contextual data supplied by the coordinator** (files, pasted metrics, enrichment summaries)—only to produce **advisory flags**, not trades.

**Advisory proposes; the system decides. Transport executes.**

Deterministic gates (spread math, RR, PMP, playbook policy, paper execution gate, MCP paper gate) remain the decision owner. Advisor output does not short-circuit that chain.

---

## Allowed interpretation

When context is present, the skill may interpret signals such as:

- Macro SPX context  
- Option Alpha economics (reward/risk, break-even framing—advisory only)  
- Assignment risk  
- Skew shape (IV vs delta)  
- PnL (as supplied—no fabrication)  
- Volatility skew, risk reversal  
- Live price levels (as supplied)  
- Earnings / OPEX / FOMC alerts (as supplied)  
- IV percentile, 1M IV / 1M RV  
- Next expiration delta, gamma, call volume, put volume  
- Proximity to call/put wall  
- GARCH rank, IV rank  
- Risk reversal rank/percentile, call/put skew percentile  
- RSI, Bollinger Band %

Missing fields are **not** inferred. Report gaps and stop.

---

## Advisory outputs

Emit exactly one primary label per review (coordinator may request a short memo alongside):

| Label | Meaning |
|-------|---------|
| `ADVISORY_OK` | Context supports continuing analysis; no elevated caution |
| `ADVISORY_CAUTION` | Elevated concern; coordinator should tighten review |
| `ADVISORY_DOWNGRADE` | Recommend lower confidence or stricter posture |
| `ADVISORY_SKIP` | Recommend no structural continuation on supplied context |

Bounded spread **suggestions** (if asked) stay within canonical structures in [system-identity.md](./system-identity.md#structure-policy)—proposals only.

---

## Forbidden authority

Claude Advisor may **not**:

- Approve, size, submit, close, cancel, or replace orders  
- Call Alpaca transport or MCP order tools  
- Mutate gates or thresholds  
- Override PMP, RR, or EV checks  
- Create or edit execution payloads  
- Spawn subagents or delegate to other skills autonomously  

If blocked or under-specified: **report and stop.** Do not invent fallback data or behavior.

---

## Coordinator packet

The coordinator should attach:

1. Paths or paste of context data to interpret  
2. Question or decision surface (e.g. “flag only”, “memo + ADVISORY_*”)  
3. Explicit reference docs per [subagency-proof.md](./subagency-proof.md#skill-reference-map) (defaults listed in [claude-advisor-context.md](./claude-advisor-context.md))

Without (1), the skill reports missing data and stops.

---

## Post-ORB advisory vs. backtest blueprint (AGENT-SKILLS-C2)

Morning and post-ORB review use the **operator artifact chain** ([evidence_artifacts_guide.md](./evidence_artifacts_guide.md)): ORB manifest → context / candidates / expressions → risk audit → `claude_brief` → optional Tier 3 `*_ideas.json` distillation ([skills/claude-advisor-distillation.md](./skills/claude-advisor-distillation.md)).

Claude Advisor must **not** point coordinators at **C4A blueprint replay** Python examples or `alpaca_blueprint_replay_plan.csv` unless the packet is explicitly a backtest / replay packet. Those tools plan historical SG-BT windows; they do not produce post-ORB idea votes or replace `scripts/orb_morning_loop.py` outputs.

For chain/OI reads on the advisory path, use manifest-linked **context** and **expressions** artifacts, or read-only `scripts/alpaca_fetch.py`—not `examples/alpaca_blueprint_replay_inputs.py`.
