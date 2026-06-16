# Packet Ownership Check: [PACKET-ID]

## Packet

## Files inspected

## Ownership checks

| Check | Result | Notes |
|---|---|---|
| Ownership ledger exists |  |  |
| Handoff log exists |  |  |
| Acceptance file exists |  |  |
| Each task has owner |  |  |
| Each task has output artifact |  |  |
| Each task has handoff target |  |  |
| Each task has acceptance check |  |  |
| No owner has unauthorized authority |  |  |

## Boundary checks

| Check | Result | Notes |
|---|---|---|
| Claude did not mutate repo directly |  |  |
| Subagents did not approve |  |  |
| Subagents did not size |  |  |
| Subagents did not call MCP |  |  |
| Natural-language prompt did not become action |  |  |
| Cursor stayed within allowed paths |  |  |
| Reconciliation did not fix by moving order |  |  |

## Final status

```text
RECON_PASS
RECON_PASS_WITH_NOTES
RECON_FAIL
```

Reconciliation can find the break. It cannot fix the break by moving an order.
