# Packet Owners: [PACKET-ID]

## Packet

## Date

## Scope

## Owner table

| Step | Owner | Task | Output artifact | Handoff target | Acceptance check |
|---|---|---|---|---|---|
| 1 | COORDINATOR | Define packet objective and source-of-truth files | Packet text | CURSOR | Objective is bounded |
| 2 | CURSOR | Create allowed repo files | Changed files | SUBAGENT_RECONCILIATION | Only allowed paths changed |
| 3 | CLAUDE | Produce advisory synthesis if assigned | Advisory file | CURSOR | No forbidden authority language |
| 4 | SUBAGENT_RECONCILIATION | Check artifacts and boundaries | Reconciliation file | COORDINATOR | RECON_PASS / NOTES / FAIL |
| 5 | ADMIN | Review acceptance packet | Acceptance file | COORDINATOR | Approve / request fixes / reject |

## Explicit non-owners

| Area | Non-owner |
|---|---|
| Approval | Claude, subagents, MCP |
| Repo mutation | Claude, subagents, MCP |
| Transport | Claude, subagents, natural-language prompts |
| Gate changes | Claude, subagents, Cursor unless separately packeted |
| Schema changes | Claude, subagents, Cursor unless separately packeted |

## Notes
