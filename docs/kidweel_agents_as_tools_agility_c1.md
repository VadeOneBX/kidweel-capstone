# KIDWEEL-PROOF-AGENTS-AS-TOOLS-AGILITY-C1

## Proof language

Kidweel separates **control** from **agility**.

- **Guardrails** and **operator approval** define what the system is allowed to do.
- **Agents-as-tools** (typed advisory agents) define how quickly specialized work is evaluated without making every specialist an execution actor.

Narrow agents, typed outputs, deterministic gates, human command at action boundaries. Advisory agents and **claude-advisor** emit memos only—they do not approve, size, submit, or bypass gates. **Cursor mobile** and **Claude mobile** are review/implementation surfaces, not the runtime command boundary.

## Stack

| Layer | Components |
|-------|------------|
| Control | `qops.guardrails`, paper-only checks, `qops.execution.hitl_paper_transport`, audit JSON |
| Agility | `qops.agents.*` specialists + `coordinator.py` |
| Evidence | Guardrail artifacts, HITL artifacts, coordinator trace |

## Specialists (tools)

| Agent | Output | Allowed `gate_status` |
|-------|--------|------------------------|
| `squeeze_candidate` | `SqueezeCandidateMemo` | PASS, WATCH, CLEAN_REJECT, NO_VIABLE_EXPRESSION |
| `vrp_candidate` | `VRPCandidateMemo` | PASS, WATCH, CLEAN_REJECT, NO_VIABLE_EXPRESSION |
| `reverse_vrp_candidate` | `ReverseVRPCandidateMemo` | + SOURCE_ABSENT when `gamma_ratio` absent |
| `risk_audit` | Policy check before guardrails | Cannot promote WATCH→PASS or approve transport |

## Coordinator

- Invokes specialists as typed tools (`invoke_specialist_tool` / `coordinator_evaluate`).
- Ranks memos (PASS first, then WATCH, …).
- Routes through **risk audit → guardrails → HITL status** via `route_memo_through_control_stack`.
- **Cannot** submit orders, override guardrails, or self-approve.

## OpenAI Agents SDK

Optional: `try_openai_agents_tool_wrapper` detects SDK; repo-local callables are canonical.

## Non-goals

No broker submission. No live execution. No autonomous approval.
