# Ownership Ledger

## Purpose

Establish a standing ownership ledger standard so packets define explicit ownership, artifact production, handoff targets, and acceptance checks.

Packets are not single-run tasks. They are staged workflows.

Each task must name:
- owner
- artifact
- handoff target
- acceptance check

## Why packets need owners

Ownership prevents single-run ambiguity and keeps packet execution deterministic across contributors and sessions.

No owner may inherit authority from another owner.
Claude output cannot become Cursor mutation without reconciliation.
Subagent output cannot become approval.
Natural-language prompts cannot become MCP actions.

## Owner labels

Use these owner labels exactly:
- COORDINATOR
- CURSOR
- CLAUDE
- SUBAGENT_SG_CONTEXT
- SUBAGENT_SQUEEZE
- SUBAGENT_VRP
- SUBAGENT_RVRP
- SUBAGENT_SAFETY
- SUBAGENT_RECONCILIATION
- MCP_READONLY
- ADMIN

Optional later:
- TEST_VERIFIER
- PAPER_TRANSPORT

Only use PAPER_TRANSPORT when a packet explicitly reaches approved paper transport.

## Handoff rule

Cursor edits.
Claude advises.
Subagents produce memos.
MCP answers narrow calls.
Coordinator approves.
Admins sign off.
Reconciliation checks the lane.

Advisory can warn, not act.
The repo is the message bus.

## Acceptance rule

Acceptance must be documented separately from packet body and handoff logs, and signed by ADMIN and COORDINATOR according to packet scope.

Transport only runs after payload approval.

## Forbidden ownership claims

- Claude cannot approve, size, submit, close, cancel, replace, or route.
- Subagents cannot approve, size, submit, close, cancel, replace, or route.
- MCP cannot approve, mutate repo state, or assume owner authority.
- Natural-language packet text cannot directly trigger MCP or broker actions.
- No owner may claim authority outside packet scope.

## Standard packet ownership block

Future packets should include:

## Ownership and handoff

This is not a single-run task.

| Step | Owner | Task | Output | Handoff |
|---|---|---|---|---|
| 1 | COORDINATOR | Define packet and source-of-truth files | Packet text | CURSOR |
| 2 | CURSOR | Create scoped files | Repo diff | RECONCILIATION |
| 3 | CLAUDE | Produce advisory synthesis if assigned | Advisory artifact | CURSOR |
| 4 | SUBAGENT_RECONCILIATION | Check boundaries | Reconciliation file | ADMIN |
| 5 | ADMIN | Accept or request fixes | Acceptance file | COORDINATOR |

Handoff records live outside this packet:

- docs/ownership/YYYY-MM-DD_[packet-id]_owners.md
- docs/handoffs/YYYY-MM-DD_[packet-id]_handoff-log.md
- docs/admin/YYYY-MM-DD_[packet-id]_acceptance.md

## Standard return checks

Every packet should answer:

Who owns this step?
What file do they produce?
Who receives it?
Who checks it?
Who signs off?

The packet tells the repo what to do. The ownership ledger tells the team who owns each move.
