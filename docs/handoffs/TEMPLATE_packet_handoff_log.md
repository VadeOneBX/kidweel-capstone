# Packet Handoff Log: [PACKET-ID]

## Packet

## Date

## Handoff sequence

| Handoff | From | To | Artifact | Purpose | Status |
|---|---|---|---|---|---|
| 1 | COORDINATOR | CURSOR | Packet text | Create scoped files | PENDING |
| 2 | CURSOR | CLAUDE | docs/handoffs/[date]_[packet]_cursor_to_claude.md | Advisory review if needed | PENDING |
| 3 | CLAUDE | CURSOR | docs/handoffs/[date]_[packet]_claude_to_cursor.md | Advisory response | PENDING |
| 4 | CURSOR | SUBAGENT_RECONCILIATION | changed files | Boundary check | PENDING |
| 5 | SUBAGENT_RECONCILIATION | ADMIN | docs/admin/[date]_[packet]_acceptance.md | Sign-off | PENDING |

## Required handoff files

```text
docs/handoffs/YYYY-MM-DD_[packet-id]_cursor_to_claude.md
docs/handoffs/YYYY-MM-DD_[packet-id]_claude_to_cursor.md
docs/reconciliation/YYYY-MM-DD_[packet-id]_reconciliation.md
docs/admin/YYYY-MM-DD_[packet-id]_acceptance.md
```

## Handoff status values

```text
PENDING
COMPLETE
BLOCKED
REQUIRES_FIX
SKIPPED_NOT_NEEDED
```

## Boundary note

A handoff is not approval. A handoff is a record that an artifact moved from one owner to another.
